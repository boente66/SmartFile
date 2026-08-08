from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Callable

from app.errors.transport_exceptions import (
    TransportCancelledError,
    TransportConfigurationError,
    TransportModeNotImplementedError,
    TransportRetryableError,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.organization_transport_repository import OrganizationTransportRepository
from app.services.audit_service import AuditService
from app.services.document_storage_service import DocumentStorageService
from app.services.organization_feature_service import OrganizationFeatureService
from app.transport.nas_transport_adapter import NASTransportAdapter
from app.transport.transport_job_queue import TransportJobQueue
from app.transport.transport_models import (
    TransportJob,
    TransportJobStatus,
    TransportOperation,
    TransportResult,
    TransportUploadRequest,
)

logger = logging.getLogger(__name__)


class CorporateTransportService:
    """Orquestra jobs empresariais sem substituir storage ou Cloud Layer."""

    MAX_ATTEMPTS = 5

    def __init__(self, database, storage_service: DocumentStorageService | None = None):
        self.database = database
        self.documents = DocumentRepository(database=database)
        self.organizations = OrganizationRepository(database=database)
        self.settings = OrganizationTransportRepository(database=database)
        self.features = OrganizationFeatureService(database)
        self.queue = TransportJobQueue(database)
        self.audit = AuditService(database)
        self.storage = storage_service or DocumentStorageService(database.paths)
        if not getattr(database, "_transport_jobs_recovered", False):
            recovered = self.queue.repository.recover_interrupted()
            database._transport_jobs_recovered = True
            if recovered:
                logger.warning(
                    "corporate.transport.jobs_recovered count=%s", recovered,
                )

    def enqueue_upload(
        self, document_id: int, organization_id: int,
        *, actor_user_id: int | None = None,
    ) -> TransportJob | None:
        if not self.is_nas_enabled(organization_id):
            return None
        document = self.documents.find_by_id(document_id, organization_id)
        if document is None or document.status != "ACTIVE":
            raise TransportConfigurationError("Documento não encontrado na organização.")
        existing = self.queue.repository.find_active(
            organization_id, document_id, str(TransportOperation.UPLOAD),
        )
        job = self.queue.enqueue_upload(organization_id, document_id)
        if existing is None:
            self._audit(
                "TRANSPORT_JOB_CREATED", job, actor_user_id,
                "Upload NAS adicionado à fila.",
            )
            self._log(job, "created")
        return job

    def prepare_document_delete(
        self, document_id: int, organization_id: int,
        *, actor_user_id: int | None = None,
    ) -> TransportJob | None:
        self.queue.repository.cancel_uploads(organization_id, document_id)
        uploaded = self.queue.repository.latest_completed_upload(
            organization_id, document_id,
        )
        if uploaded is None or not uploaded.remote_path:
            return None
        existing = self.queue.repository.find_active(
            organization_id, document_id, str(TransportOperation.DELETE),
        )
        job = self.queue.enqueue_delete(
            organization_id, document_id, uploaded.remote_path,
        )
        if existing is None:
            self._audit(
                "TRANSPORT_JOB_CREATED", job, actor_user_id,
                "Exclusão NAS adicionada à fila.",
            )
            self._log(job, "created")
        return job

    def is_nas_enabled(self, organization_id: int) -> bool:
        organization = self.organizations.find_by_id(organization_id)
        if organization is None or organization.status != "ACTIVE":
            return False
        if organization.profile_code != "BUSINESS":
            return False
        if not self.features.for_organization(organization).has("server_transport"):
            return False
        setting = self.settings.get(organization_id)
        return bool(setting.enabled and setting.mode == "NAS" and setting.endpoint)

    def process_next(
        self, organization_id: int,
        progress_callback: Callable[[int, str], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> TransportJob | None:
        job = self.queue.next_pending(organization_id)
        if job is None:
            return None
        return self.process_job(
            job.id, progress_callback, cancellation_requested,
        )

    def process_pending(
        self, organization_id: int,
        progress_callback: Callable[[int, str], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
        limit: int = 100,
    ) -> dict[str, int]:
        jobs = self.queue.list_pending(organization_id, limit)
        summary = {
            "jobs": 0, "completed": 0, "retry": 0,
            "failed": 0, "cancelled": 0,
        }
        for index, job in enumerate(jobs):
            if cancellation_requested and cancellation_requested():
                break
            base = int((index / max(1, len(jobs))) * 100)
            result = self.process_job(
                job.id,
                lambda value, message, base=base, total=len(jobs): (
                    progress_callback(
                        min(99, base + int(value / max(1, total))), message,
                    ) if progress_callback else None
                ),
                cancellation_requested,
            )
            summary["jobs"] += 1
            key = result.status.casefold()
            if key in summary:
                summary[key] += 1
        if progress_callback:
            progress_callback(100, "Transporte corporativo concluído")
        return summary

    def process_job(
        self, job_id: int,
        progress_callback: Callable[[int, str], None] | None = None,
        cancellation_requested: Callable[[], bool] | None = None,
    ) -> TransportJob:
        job = self.queue.get(job_id)
        if not self.queue.repository.mark_running(job_id):
            return self.queue.get(job_id)
        job = self.queue.get(job_id)
        self._log(job, "running")
        try:
            if cancellation_requested and cancellation_requested():
                raise TransportCancelledError("Operação cancelada antes da transferência.")
            adapter = self._adapter_for_job(job)
            if job.operation == TransportOperation.UPLOAD:
                result = self._upload(
                    adapter, job, progress_callback, cancellation_requested,
                )
            elif job.operation == TransportOperation.DELETE:
                if not job.remote_path:
                    raise TransportConfigurationError(
                        "Job de exclusão sem caminho remoto."
                    )
                result = adapter.delete(job.remote_path)
            else:
                raise TransportConfigurationError("Operação de transporte inválida.")
            if not self.queue.repository.complete(job.id, result.remote_path):
                if result.remote_path and job.operation == TransportOperation.UPLOAD:
                    try:
                        adapter.delete(result.remote_path)
                    except Exception:
                        logger.exception(
                            "corporate.transport.cancelled_cleanup_failed "
                            "organization_id=%s document_id=%s job_id=%s",
                            job.organization_id, job.document_id, job.id,
                        )
                return self.queue.get(job.id)
            completed = self.queue.get(job.id)
            action = (
                "TRANSPORT_UPLOAD_COMPLETED"
                if job.operation == TransportOperation.UPLOAD
                else "TRANSPORT_DELETE_COMPLETED"
            )
            self._audit(action, completed, None, result.message)
            self._log(completed, "completed")
            return completed
        except TransportCancelledError as exc:
            self.queue.repository.cancel(job.id, self._safe_error(exc))
            cancelled = self.queue.get(job.id)
            self._log(cancelled, "cancelled")
            return cancelled
        except TransportRetryableError as exc:
            failed = self.queue.repository.fail(
                job.id, self._safe_error(exc), self.MAX_ATTEMPTS,
            )
            self._record_failure(failed)
            return failed
        except TransportConfigurationError as exc:
            failed = self.queue.repository.fail_definitive(
                job.id, self._safe_error(exc),
            )
            self._record_failure(failed)
            return failed
        except Exception as exc:
            logger.exception(
                "corporate.transport.unexpected_failure organization_id=%s "
                "document_id=%s job_id=%s operation=%s attempt=%s",
                job.organization_id, job.document_id, job.id,
                job.operation, job.attempts,
            )
            failed = self.queue.repository.fail_definitive(
                job.id, "Falha inesperada no transporte corporativo.",
            )
            self._record_failure(failed)
            return failed

    def retry_failed(self, organization_id: int) -> int:
        return self.queue.repository.retry_failed(organization_id)

    def test_connection(
        self, organization_id: int, *, mode: str | None = None,
        endpoint: str | None = None, actor_user_id: int | None = None,
    ) -> TransportResult:
        organization = self.organizations.find_by_id(organization_id)
        if organization is None or organization.status != "ACTIVE":
            raise TransportConfigurationError("Organização não encontrada.")
        self.features.require(organization, "server_transport")
        setting = self.settings.get(organization_id)
        selected_mode = (mode or setting.mode).strip().upper()
        selected_endpoint = endpoint if endpoint is not None else setting.endpoint
        try:
            adapter = self._adapter(
                selected_mode, selected_endpoint,
                self._organization_segment(organization),
            )
            result = adapter.test_connection()
        except TransportConfigurationError as exc:
            result = TransportResult(False, self._safe_error(exc))
        self.audit.record(
            "TRANSPORT_CONNECTION_TESTED", user_id=actor_user_id,
            organization_id=organization_id, target_type="transport",
            target_id=organization_id,
            description=("Conectado: " if result.success else "Falha: ") + result.message,
        )
        logger.info(
            "corporate.transport.connection_test organization_id=%s mode=%s success=%s",
            organization_id, selected_mode, result.success,
        )
        return result

    def summary(self, organization_id: int) -> dict:
        setting = self.settings.get(organization_id)
        counts = self.queue.repository.counts(organization_id)
        last = self.database.fetch_one(
            """
            SELECT description, created_at FROM audit_log
            WHERE organization_id=? AND action='TRANSPORT_CONNECTION_TESTED'
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id,),
        )
        return {
            "mode": setting.mode,
            "enabled": setting.enabled,
            "last_test_at": last["created_at"] if last else None,
            "last_test_message": last["description"] if last else None,
            **counts,
        }

    def _upload(
        self, adapter, job: TransportJob,
        progress_callback: Callable[[int, str], None] | None,
        cancellation_requested: Callable[[], bool] | None,
    ) -> TransportResult:
        if not self.is_nas_enabled(job.organization_id):
            raise TransportConfigurationError(
                "O transporte NAS não está habilitado para a organização."
            )
        document = self.documents.find_by_id(job.document_id, job.organization_id)
        if document is None or document.status != "ACTIVE":
            raise TransportConfigurationError("Documento local não encontrado.")
        local_path = document.storage_path or document.path
        if not local_path or not self.storage.exists(local_path):
            raise TransportConfigurationError(
                "Arquivo local gerenciado não encontrado."
            )
        return adapter.upload(TransportUploadRequest(
            local_path=Path(local_path),
            remote_name=self._remote_name(document.id, document.name),
            expected_checksum=document.checksum,
            progress_callback=(
                lambda copied, total: progress_callback(
                    int((copied / max(1, total)) * 100),
                    f"Enviando documento {document.id} ao NAS",
                ) if progress_callback else None
            ),
            cancellation_requested=cancellation_requested,
        ))

    def _adapter_for_job(self, job: TransportJob):
        organization = self.organizations.find_by_id(job.organization_id)
        if organization is None or organization.status != "ACTIVE":
            raise TransportConfigurationError("Organização do job não encontrada.")
        setting = self.settings.get(job.organization_id)
        return self._adapter(
            job.transport_mode, setting.endpoint,
            self._organization_segment(organization),
        )

    @staticmethod
    def _adapter(mode: str, endpoint: str | None, organization_segment: str):
        selected = (mode or "").strip().upper()
        if selected == "NAS":
            return NASTransportAdapter(endpoint or "", organization_segment)
        if selected in {"HTTPS", "LAN"}:
            raise TransportModeNotImplementedError(
                f"Conector real ainda não implementado para o modo {selected}."
            )
        raise TransportConfigurationError("Modo de transporte físico inválido.")

    @staticmethod
    def _organization_segment(organization) -> str:
        slug = re.sub(r"[^A-Za-z0-9._-]+", "-", organization.slug or "organization")
        slug = slug.strip("-._") or "organization"
        return f"{slug}-{int(organization.id)}"

    @staticmethod
    def _remote_name(document_id: int, logical_name: str) -> str:
        normalized = unicodedata.normalize("NFKC", logical_name or "documento")
        normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f]+", "_", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" .") or "documento"
        return f"{int(document_id)}_{normalized[:180]}"

    def _record_failure(self, job: TransportJob) -> None:
        action = (
            "TRANSPORT_UPLOAD_FAILED"
            if job.operation == TransportOperation.UPLOAD
            else "TRANSPORT_DELETE_FAILED"
        )
        self._audit(action, job, None, job.last_error or "Falha no transporte.")
        self._log(job, "failed")

    def _audit(
        self, action: str, job: TransportJob, user_id: int | None, description: str,
    ) -> None:
        self.audit.record(
            action, user_id=user_id, organization_id=job.organization_id,
            target_type="transport_job", target_id=job.id,
            description=description,
        )

    @staticmethod
    def _safe_error(error: Exception) -> str:
        return (str(error).strip() or "Falha no transporte corporativo.")[:500]

    @staticmethod
    def _log(job: TransportJob, event: str) -> None:
        logger.info(
            "corporate.transport.job.%s organization_id=%s document_id=%s "
            "job_id=%s mode=%s operation=%s status=%s attempt=%s",
            event, job.organization_id, job.document_id, job.id,
            job.transport_mode, job.operation, job.status, job.attempts,
        )
