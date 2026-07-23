from __future__ import annotations

import os
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from app.cloud.cloud_job_queue import CloudJobQueue
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import (
    CloudFolderMapping, CloudOperation, CloudSyncState, CloudUploadRequest, SyncJob,
)
from app.cloud.cloud_provider import (
    CloudAuthenticationError,
    CloudConflictError,
    CloudOfflineError,
    CloudRateLimitError,
    CloudResourceNotFoundError,
)
from app.database.database import Database
from app.errors.storage_exceptions import CloudStorageLimitError
from app.repositories.cloud_folder_repository import CloudFolderRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.folder_repository import FolderRepository
from app.repositories.organization_repository import OrganizationRepository
from app.services.storage_quota_service import StorageQuotaService

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], None]


class CloudSyncService:
    def __init__(self, database: Database, manager: CloudManager | None = None):
        self.database = database
        self.manager = manager or CloudManager(database)
        self.queue = CloudJobQueue(database)
        self.documents = DocumentRepository(database=database)
        self.quota = StorageQuotaService(database)
        self.folder_mappings = CloudFolderRepository(database=database)
        self.folders = FolderRepository(database=database)
        self.organizations = OrganizationRepository(database=database)

    def enqueue_upload(self, document_id: int, organization_id: int) -> SyncJob | None:
        settings = self.manager.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.paused or settings.cloud_account_id is None:
            self.documents.update_cloud_state(document_id, CloudSyncState.LOCAL_ONLY)
            return None
        self.documents.update_cloud_state(document_id, CloudSyncState.PENDING_UPLOAD, settings.sync_mode)
        return self.queue.enqueue(document_id, CloudOperation.UPLOAD, settings.sync_mode)

    def enqueue_move(self, document_id: int, organization_id: int) -> SyncJob | None:
        settings = self.manager.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.paused or settings.cloud_account_id is None:
            return None
        document = self.documents.find_by_id(document_id, organization_id)
        if document is None:
            return None
        if not document.remote_id:
            return self.enqueue_upload(document_id, organization_id)
        return self.queue.enqueue(document_id, CloudOperation.MOVE, settings.sync_mode)

    def process_next(self, organization_id: int | None = None) -> SyncJob | None:
        job = self.queue.next_pending(organization_id)
        if job is None:
            return None
        logger.info(
            "cloud.sync.job.start job_id=%s document_id=%s operation=%s provider=%s",
            job.id, job.document_id, job.operation, job.provider,
        )
        self.queue.mark_running(job.id)
        document = self.documents.find_by_id(job.document_id)
        if document is None:
            message = "Documento local não encontrado para sincronização."
            self.queue.retry(job.id, message)
            logger.error(
                "cloud.sync.job.missing_document job_id=%s document_id=%s",
                job.id, job.document_id,
            )
            raise ValueError(message)
        try:
            provider = self.manager.provider_for(document.organization_id)
            if provider is None:
                raise CloudAuthenticationError(
                    "A conta de nuvem não está disponível. Reconecte a conta e tente novamente."
                )
            root_id = self.synchronize_structure(
                document.organization_id, provider=provider, reconcile_documents=False
            )
            if job.operation == CloudOperation.UPLOAD:
                self.documents.update_cloud_state(document.id, CloudSyncState.UPLOADING, job.provider)
                local_path = Path(document.storage_path or document.path)
                metadata = provider.upload(CloudUploadRequest(
                    local_path=local_path, remote_name=document.name,
                    remote_id=document.remote_id,
                    remote_parent_id=self._remote_parent_id(
                        document.organization_id, document.folder_id, job.provider, root_id
                    ),
                ))
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.SYNCED, job.provider, metadata.remote_id,
                    metadata.version, self._now(),
                )
            elif job.operation == CloudOperation.DOWNLOAD:
                self._download(provider, document)
            elif job.operation == CloudOperation.MOVE:
                if not document.remote_id:
                    raise ValueError("Documento remoto ausente para movimentação.")
                parent_id = self._remote_parent_id(
                    document.organization_id, document.folder_id, job.provider, root_id
                )
                metadata = provider.move(document.remote_id, parent_id)
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.SYNCED, job.provider,
                    document.remote_id, metadata.version or document.remote_version,
                    self._now(),
                )
            elif job.operation == CloudOperation.RENAME:
                if not document.remote_id:
                    raise ValueError("Documento remoto ausente para renomeação.")
                metadata = provider.rename(document.remote_id, document.name)
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.SYNCED, job.provider,
                    document.remote_id, metadata.version or document.remote_version,
                    self._now(),
                )
            elif job.operation == CloudOperation.DELETE and document.remote_id:
                provider.delete(document.remote_id)
                self.documents.update_cloud_state(document.id, CloudSyncState.LOCAL_DELETED, job.provider)
            else:
                raise ValueError(
                    f"Operação de sincronização não suportada: {job.operation}."
                )
            self.queue.complete(job.id)
            logger.info(
                "cloud.sync.job.done job_id=%s document_id=%s operation=%s",
                job.id, document.id, job.operation,
            )
        except CloudConflictError as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.CONFLICT, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
            logger.warning(
                "cloud.sync.job.conflict job_id=%s document_id=%s",
                job.id, document.id,
            )
            raise
        except (CloudOfflineError, CloudRateLimitError) as exc:
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id
            )
            self.queue.retry(job.id, str(exc))
            logger.warning(
                "cloud.sync.job.retryable_error job_id=%s document_id=%s error=%s",
                job.id, document.id, type(exc).__name__,
            )
            raise
        except CloudAuthenticationError as exc:
            self.manager.mark_reauthentication_required(document.organization_id)
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id
            )
            self.queue.retry(job.id, str(exc))
            logger.warning(
                "cloud.sync.job.authentication_error job_id=%s document_id=%s",
                job.id, document.id,
            )
            raise
        except CloudStorageLimitError as exc:
            message = (
                "O documento foi salvo no SmartFile, mas não pôde ser sincronizado "
                "porque o armazenamento da nuvem está cheio."
            )
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id
            )
            self.queue.retry(job.id, message)
            logger.warning(
                "cloud.sync.job.storage_limit job_id=%s document_id=%s",
                job.id, document.id,
            )
            raise CloudStorageLimitError(message) from exc
        except Exception as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id)
            message = str(exc).strip() or "Falha inesperada ao sincronizar o documento."
            self.queue.retry(job.id, message)
            logger.exception(
                "cloud.sync.job.failed job_id=%s document_id=%s operation=%s",
                job.id, document.id, job.operation,
            )
            raise
        return job

    def sync_changes(
        self,
        organization_id: int,
        progress: ProgressCallback | None = None,
    ) -> int:
        logger.info("cloud.sync.delta.start organization_id=%s", organization_id)
        provider = self.manager.provider_for(organization_id)
        if provider is None:
            raise CloudAuthenticationError(
                "A conta de nuvem não está disponível. Reconecte a conta e tente novamente."
            )
        self._progress(progress, 10, "Garantindo estrutura da organização")
        self.synchronize_structure(organization_id, provider=provider, reconcile_documents=True)
        self._progress(progress, 25, "Consultando alterações remotas")
        settings = self.manager.settings(organization_id)
        changes, cursor = provider.list_changes(settings.delta_token)
        self._progress(progress, 35, "Consulta remota concluída")
        for change in changes:
            if change.deleted:
                self.database.execute_query(
                    """
                    UPDATE documents SET cloud_status = 'REMOTE_DELETED', updated_at = ?
                    WHERE organization_id = ? AND remote_id = ?
                    """,
                    (self._now(), organization_id, change.remote_id),
                )
        self.database.execute_query(
            "UPDATE cloud_settings SET delta_token = ?, last_sync = ? WHERE organization_id = ?",
            (cursor, self._now(), organization_id),
        )
        logger.info(
            "cloud.sync.delta.done organization_id=%s changes=%s cursor_updated=%s",
            organization_id, len(changes), cursor != settings.delta_token,
        )
        return len(changes)

    def mark_pending_documents_failed(
        self, organization_id: int, error: str,
    ) -> int:
        """Expõe falha de sessão nos documentos sem descartar jobs repetíveis."""

        message = error.strip() or "Falha na sincronização da nuvem."
        rows = self.database.fetch_all(
            """
            SELECT DISTINCT d.id,d.cloud_provider,d.remote_id
            FROM documents d JOIN sync_jobs j ON j.document_id=d.id
            WHERE d.organization_id=?
              AND j.status IN ('PENDING','RETRY','RUNNING')
            """,
            (organization_id,),
        )
        for row in rows:
            self.documents.update_cloud_state(
                row["id"], CloudSyncState.SYNC_ERROR,
                row["cloud_provider"], row["remote_id"],
            )
        self.database.execute_query(
            """
            UPDATE sync_jobs SET
                status=CASE WHEN status='RUNNING' THEN 'RETRY' ELSE status END,
                last_error=?,updated_at=?
            WHERE id IN (
                SELECT j.id FROM sync_jobs j JOIN documents d ON d.id=j.document_id
                WHERE d.organization_id=?
                  AND j.status IN ('PENDING','RETRY','RUNNING')
            )
            """,
            (message[:1000], self._now(), organization_id),
        )
        logger.warning(
            "cloud.sync.pending_marked_failed organization_id=%s documents=%s",
            organization_id, len(rows),
        )
        return len(rows)

    def synchronize_structure(
        self, organization_id: int, *, provider=None, reconcile_documents: bool = True,
    ) -> str:
        """Espelha a organização e suas pastas lógicas sem enviar o banco SQLite."""

        provider = provider or self.manager.provider_for(organization_id)
        if provider is None:
            raise ValueError("A organização não possui sincronização ativa.")
        settings = self.manager.settings(organization_id)
        organization = self.organizations.find_by_id(organization_id)
        if organization is None or organization.status != "ACTIVE":
            raise ValueError("Organização não encontrada para sincronização.")
        provider_name = settings.sync_mode
        logger.info(
            "cloud.sync.structure.start organization_id=%s provider=%s",
            organization_id, provider_name,
        )
        organization_remote_name = self._organization_remote_name(
            organization.name, organization_id
        )

        root_id = settings.remote_root_id
        if root_id:
            try:
                metadata = provider.get_metadata(root_id)
                if metadata.name != organization_remote_name:
                    provider.rename(root_id, organization_remote_name)
            except CloudResourceNotFoundError:
                root_id = None
        if not root_id:
            logger.info(
                "cloud.sync.structure.ensure_roots organization_id=%s",
                organization_id,
            )
            application_root = provider.ensure_folder("SmartFile")
            organization_root = provider.ensure_folder(
                organization_remote_name, application_root.remote_id
            )
            root_id = organization_root.remote_id
            self.database.execute_query(
                "UPDATE cloud_settings SET remote_root_id=? WHERE organization_id=?",
                (root_id, organization_id),
            )

        all_folders = self.folders.find_all_including_deleted(organization_id)
        active = [folder for folder in all_folders if folder.status == "ACTIVE"]
        logger.info(
            "cloud.sync.structure.folders organization_id=%s active=%s",
            organization_id, len(active),
        )
        remote_by_folder: dict[int, str] = {}
        remaining = list(active)
        while remaining:
            progressed = False
            for folder in remaining[:]:
                if folder.parent_id is not None and folder.parent_id not in remote_by_folder:
                    continue
                parent_remote_id = (
                    remote_by_folder[folder.parent_id]
                    if folder.parent_id is not None else root_id
                )
                mapping = self.folder_mappings.find(
                    organization_id, folder.id, provider_name
                )
                remote = None
                if mapping:
                    try:
                        if mapping.remote_name != folder.name:
                            remote = provider.rename(mapping.remote_id, folder.name)
                        if mapping.remote_parent_id != parent_remote_id:
                            remote = provider.move(mapping.remote_id, parent_remote_id)
                    except CloudResourceNotFoundError:
                        mapping = None
                if mapping is None:
                    remote = provider.ensure_folder(folder.name, parent_remote_id)
                    remote_id = remote.remote_id
                else:
                    remote_id = mapping.remote_id
                self.folder_mappings.upsert(CloudFolderMapping(
                    organization_id=organization_id,
                    folder_id=folder.id,
                    provider=provider_name,
                    remote_id=remote_id,
                    remote_parent_id=parent_remote_id,
                    remote_name=folder.name,
                    synced_at=self._now(),
                ))
                remote_by_folder[folder.id] = remote_id
                remaining.remove(folder)
                progressed = True
            if not progressed:
                raise ValueError("A estrutura local de pastas possui referências inválidas.")

        if reconcile_documents:
            self._reconcile_documents(
                provider, organization_id, provider_name, root_id, remote_by_folder
            )
            self._remove_deleted_remote_folders(
                provider, organization_id, provider_name, all_folders
            )
        logger.info(
            "cloud.sync.structure.done organization_id=%s folders=%s",
            organization_id, len(active),
        )
        return root_id

    def _reconcile_documents(
        self, provider, organization_id: int, provider_name: str,
        root_id: str, remote_by_folder: dict[int, str],
    ) -> None:
        for document in self.documents.find_all(organization_id):
            if not document.remote_id:
                continue
            desired_parent = remote_by_folder.get(document.folder_id, root_id)
            try:
                metadata = provider.get_metadata(document.remote_id)
            except CloudResourceNotFoundError:
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.REMOTE_DELETED,
                    provider_name, document.remote_id,
                )
                continue
            if metadata.name != document.name:
                metadata = provider.rename(document.remote_id, document.name)
            if metadata.parent_id != desired_parent:
                metadata = provider.move(document.remote_id, desired_parent)
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNCED, provider_name,
                document.remote_id, metadata.version or document.remote_version,
                self._now(),
            )

    def _remove_deleted_remote_folders(
        self, provider, organization_id: int, provider_name: str, folders,
    ) -> None:
        by_id = {folder.id: folder for folder in folders}
        deleted = [folder for folder in folders if folder.status != "ACTIVE"]
        deleted.sort(key=lambda folder: self._folder_depth(folder, by_id), reverse=True)
        for folder in deleted:
            mapping = self.folder_mappings.find(
                organization_id, folder.id, provider_name
            )
            if mapping is None:
                continue
            try:
                provider.delete(mapping.remote_id)
            except CloudResourceNotFoundError:
                pass
            self.folder_mappings.delete(organization_id, folder.id, provider_name)

    def _remote_parent_id(
        self, organization_id: int, folder_id: int | None,
        provider_name: str, root_id: str,
    ) -> str:
        if folder_id is None:
            return root_id
        mapping = self.folder_mappings.find(organization_id, folder_id, provider_name)
        return mapping.remote_id if mapping else root_id

    @staticmethod
    def _folder_depth(folder, by_id) -> int:
        depth = 0
        parent_id = folder.parent_id
        visited = {folder.id}
        while parent_id is not None and parent_id not in visited:
            visited.add(parent_id)
            parent = by_id.get(parent_id)
            if parent is None:
                break
            depth += 1
            parent_id = parent.parent_id
        return depth

    @staticmethod
    def _organization_remote_name(name: str, organization_id: int) -> str:
        forbidden = '\\/:*?"<>|'
        clean = " ".join(name.split())
        for character in forbidden:
            clean = clean.replace(character, "-")
        clean = clean.strip(". ")[:96] or "Organização"
        return f"{clean} ({organization_id})"

    @staticmethod
    def _progress(
        callback: ProgressCallback | None, value: int, message: str,
    ) -> None:
        if callback is not None:
            callback(value, message)

    def _download(self, provider, document) -> None:
        if not document.remote_id:
            raise ValueError("Documento sem identificador remoto.")
        destination = Path(document.storage_path or document.path).resolve()
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.cloud.tmp")
        backup = destination.with_name(f".{destination.name}.{uuid4().hex}.cloud.bak")
        operation_id = None
        try:
            provider.download(document.remote_id, temporary)
            new_size = temporary.stat().st_size
            delta = new_size - int(document.size or 0)
            if delta > 0:
                operation_id = self.quota.reserve(document.organization_id, delta)
            if destination.exists():
                os.replace(destination, backup)
            os.replace(temporary, destination)
            try:
                with self.database.transaction():
                    document.size = new_size
                    document.checksum = self._checksum(destination)
                    document.updated_at = self._now()
                    document.cloud_status = CloudSyncState.SYNCED
                    document.last_synced_at = self._now()
                    self.documents.update(document)
                    if operation_id:
                        self.quota.commit_reservation(operation_id)
                    elif delta < 0:
                        self.quota.release_used(document.organization_id, -delta)
                backup.unlink(missing_ok=True)
            except Exception:
                destination.unlink(missing_ok=True)
                if backup.exists():
                    os.replace(backup, destination)
                raise
        except Exception:
            if operation_id:
                self.quota.release_reservation(operation_id)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
