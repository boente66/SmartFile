from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.cloud.cloud_job_queue import CloudJobQueue
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import CloudOperation, CloudSyncState, CloudUploadRequest, SyncJob
from app.cloud.cloud_provider import CloudConflictError, CloudOfflineError
from app.database.database import Database
from app.repositories.document_repository import DocumentRepository


class CloudSyncService:
    def __init__(self, database: Database, manager: CloudManager | None = None):
        self.database = database
        self.manager = manager or CloudManager(database)
        self.queue = CloudJobQueue(database)
        self.documents = DocumentRepository(database=database)

    def enqueue_upload(self, document_id: int, organization_id: int) -> SyncJob | None:
        settings = self.manager.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.paused or settings.cloud_account_id is None:
            self.documents.update_cloud_state(document_id, CloudSyncState.LOCAL_ONLY)
            return None
        self.documents.update_cloud_state(document_id, CloudSyncState.PENDING_UPLOAD, settings.sync_mode)
        return self.queue.enqueue(document_id, CloudOperation.UPLOAD, settings.sync_mode)

    def process_next(self) -> SyncJob | None:
        job = self.queue.next_pending()
        if job is None:
            return None
        self.queue.mark_running(job.id)
        document = self.documents.find_by_id(job.document_id)
        if document is None:
            self.queue.retry(job.id, "Documento local não encontrado.")
            return job
        provider = self.manager.provider_for(document.organization_id)
        if provider is None:
            self.queue.retry(job.id, "Sincronização local ou pausada.")
            return job
        try:
            if job.operation == CloudOperation.UPLOAD:
                self.documents.update_cloud_state(document.id, CloudSyncState.UPLOADING, job.provider)
                local_path = Path(document.storage_path or document.path)
                metadata = provider.upload(CloudUploadRequest(
                    local_path=local_path, remote_name=document.name,
                    remote_id=document.remote_id,
                    remote_parent_id=self.manager.settings(document.organization_id).remote_root_id,
                ))
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.SYNCED, job.provider, metadata.remote_id,
                    metadata.version, self._now(),
                )
            elif job.operation == CloudOperation.DOWNLOAD:
                self._download(provider, document)
            elif job.operation == CloudOperation.DELETE and document.remote_id:
                provider.delete(document.remote_id)
                self.documents.update_cloud_state(document.id, CloudSyncState.LOCAL_DELETED, job.provider)
            self.queue.complete(job.id)
        except CloudConflictError as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.CONFLICT, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
        except CloudOfflineError as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.PENDING_UPLOAD, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
        except Exception as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.ERROR, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
        return job

    def sync_changes(self, organization_id: int) -> int:
        provider = self.manager.provider_for(organization_id)
        if provider is None:
            return 0
        settings = self.manager.settings(organization_id)
        changes, cursor = provider.list_changes(settings.delta_token)
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
        return len(changes)

    def _download(self, provider, document) -> None:
        if not document.remote_id:
            raise ValueError("Documento sem identificador remoto.")
        destination = Path(document.storage_path or document.path).resolve()
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.cloud.tmp")
        try:
            provider.download(document.remote_id, temporary)
            os.replace(temporary, destination)
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNCED, document.cloud_provider,
                document.remote_id, document.remote_version, self._now(),
            )
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
