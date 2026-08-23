from __future__ import annotations

from datetime import datetime, timezone

from app.cloud.cloud_models import (
    CloudFolderManagementMode, CloudFolderMapping, RemoteItemType, RemoteMetadata,
)
from app.cloud.cloud_provider import CloudAuthenticationError
from app.cloud.cloud_manager import CloudManager
from app.database.database import Database
from app.errors.cloud_folder_mapping_exceptions import (
    CloudFolderMappingConflictError, CloudFolderMappingError,
    InvalidRemoteFolderError,
)
from app.repositories.cloud_folder_repository import CloudFolderRepository
from app.repositories.folder_repository import FolderRepository
from app.services.audit_service import AuditService


class CloudFolderMappingService:
    """Adota identidades remotas sem assumir controle da árvore do usuário."""

    def __init__(self, database: Database, manager: CloudManager):
        self.database = database
        self.manager = manager
        self.mappings = CloudFolderRepository(database=database)
        self.folders = FolderRepository(database=database)
        self.audit = AuditService(database)

    def current(self, organization_id: int, folder_id: int) -> CloudFolderMapping | None:
        settings = self.manager.settings(organization_id)
        if settings.sync_mode != "ONEDRIVE":
            return None
        mapping = self.mappings.find(organization_id, folder_id, settings.sync_mode)
        if mapping is None:
            return None
        if (
            mapping.cloud_account_id is not None
            and mapping.cloud_account_id != settings.cloud_account_id
        ):
            return None
        return mapping

    def map_existing_onedrive_folder(
        self,
        organization_id: int,
        folder_id: int,
        remote_id: str,
        *,
        provider=None,
    ) -> CloudFolderMapping:
        self.manager._require("cloud.sync")
        settings = self.manager.settings(organization_id)
        if settings.sync_mode != "ONEDRIVE" or settings.cloud_account_id is None:
            raise CloudAuthenticationError(
                "Conecte uma conta OneDrive nesta organização antes de mapear a pasta."
            )
        folder = self.folders.find_by_id(folder_id, organization_id)
        if folder is None or folder.status != "ACTIVE":
            raise CloudFolderMappingError(
                "Selecione uma pasta lógica ativa da organização."
            )
        clean_remote_id = str(remote_id or "").strip()
        if not clean_remote_id:
            raise InvalidRemoteFolderError("A pasta remota selecionada é inválida.")
        provider = provider or self.manager.provider_for(organization_id)
        if provider is None:
            raise CloudAuthenticationError("A conta OneDrive não está disponível.")
        metadata: RemoteMetadata = provider.get_metadata(clean_remote_id)
        if metadata.deleted or metadata.item_type != RemoteItemType.FOLDER:
            raise InvalidRemoteFolderError(
                "O item selecionado não é uma pasta existente do OneDrive."
            )
        duplicate = self.mappings.find_by_remote_id(
            organization_id, settings.cloud_account_id, "ONEDRIVE", metadata.remote_id,
        )
        if duplicate is not None and duplicate.folder_id != folder_id:
            duplicate_folder = self.folders.find_by_id(
                duplicate.folder_id, organization_id
            )
            name = duplicate_folder.name if duplicate_folder else f"#{duplicate.folder_id}"
            raise CloudFolderMappingConflictError(
                f"Esta pasta do OneDrive já está mapeada para {name}."
            )
        mapping = CloudFolderMapping(
            organization_id=organization_id,
            folder_id=folder_id,
            provider="ONEDRIVE",
            remote_id=metadata.remote_id,
            remote_parent_id=metadata.parent_id,
            remote_name=metadata.name,
            synced_at=self._now(),
            cloud_account_id=settings.cloud_account_id,
            management_mode=CloudFolderManagementMode.ADOPTED,
        )
        with self.database.transaction():
            self.mappings.upsert(mapping)
            self.audit.record(
                "CLOUD_FOLDER_MAPPED",
                user_id=getattr(
                    getattr(self.manager.session_context, "current_user", None), "id", None
                ),
                organization_id=organization_id,
                target_type="folder",
                target_id=folder_id,
                description="Pasta lógica associada a pasta existente do OneDrive",
            )
        return mapping

    def remove_mapping(self, organization_id: int, folder_id: int) -> bool:
        self.manager._require("cloud.sync")
        settings = self.manager.settings(organization_id)
        mapping = self.mappings.find(organization_id, folder_id, "ONEDRIVE")
        if mapping is None:
            return False
        if (
            mapping.cloud_account_id is not None
            and mapping.cloud_account_id != settings.cloud_account_id
        ):
            raise CloudFolderMappingConflictError(
                "O mapeamento pertence a outra conta OneDrive e não pode ser alterado."
            )
        with self.database.transaction():
            removed = self.mappings.delete(organization_id, folder_id, "ONEDRIVE")
            if removed:
                self.audit.record(
                    "CLOUD_FOLDER_UNMAPPED",
                    user_id=getattr(
                        getattr(self.manager.session_context, "current_user", None), "id", None
                    ),
                    organization_id=organization_id,
                    target_type="folder",
                    target_id=folder_id,
                    description="Associação com pasta OneDrive removida; conteúdo remoto preservado",
                )
        return removed

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
