from __future__ import annotations

import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
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
        self.queue.mark_running(job.id)
        document = self.documents.find_by_id(job.document_id)
        if document is None:
            self.queue.retry(job.id, "Documento local não encontrado.")
            return job
        try:
            provider = self.manager.provider_for(document.organization_id)
            if provider is None:
                self.queue.retry(job.id, "Sincronização local ou pausada.")
                return job
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
                if document.remote_id:
                    parent_id = self._remote_parent_id(
                        document.organization_id, document.folder_id, job.provider, root_id
                    )
                    metadata = provider.move(document.remote_id, parent_id)
                    self.documents.update_cloud_state(
                        document.id, CloudSyncState.SYNCED, job.provider,
                        document.remote_id, metadata.version or document.remote_version,
                        self._now(),
                    )
            elif job.operation == CloudOperation.RENAME and document.remote_id:
                metadata = provider.rename(document.remote_id, document.name)
                self.documents.update_cloud_state(
                    document.id, CloudSyncState.SYNCED, job.provider,
                    document.remote_id, metadata.version or document.remote_version,
                    self._now(),
                )
            elif job.operation == CloudOperation.DELETE and document.remote_id:
                provider.delete(document.remote_id)
                self.documents.update_cloud_state(document.id, CloudSyncState.LOCAL_DELETED, job.provider)
            self.queue.complete(job.id)
        except CloudConflictError as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.CONFLICT, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
        except (CloudOfflineError, CloudRateLimitError) as exc:
            pending_state = (
                CloudSyncState.PENDING_DOWNLOAD
                if job.operation == CloudOperation.DOWNLOAD
                else CloudSyncState.PENDING_UPLOAD
            )
            self.documents.update_cloud_state(
                document.id, pending_state, job.provider, document.remote_id
            )
            self.queue.retry(job.id, str(exc))
        except CloudAuthenticationError as exc:
            self.manager.mark_reauthentication_required(document.organization_id)
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id
            )
            self.queue.retry(job.id, str(exc))
        except CloudStorageLimitError:
            message = (
                "O documento foi salvo no SmartFile, mas não pôde ser sincronizado "
                "porque o armazenamento da nuvem está cheio."
            )
            self.documents.update_cloud_state(
                document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id
            )
            self.queue.retry(job.id, message)
        except Exception as exc:
            self.documents.update_cloud_state(document.id, CloudSyncState.SYNC_ERROR, job.provider, document.remote_id)
            self.queue.retry(job.id, str(exc))
        return job

    def sync_changes(self, organization_id: int) -> int:
        provider = self.manager.provider_for(organization_id)
        if provider is None:
            return 0
        self.synchronize_structure(organization_id, provider=provider, reconcile_documents=True)
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
