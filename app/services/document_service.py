from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace
from typing import Optional
from uuid import uuid4

from app.database.database import Database
from app.entities.document_entity import DocumentEntity
from app.errors.persistence_exceptions import (
    DuplicateDocumentError,
    InvalidDocumentError,
    StorageError,
)
from app.models.document_model import DocumentModel
from app.repositories.document_repository import DocumentRepository
from app.services.history_service import HistoryService
from app.services.document_storage_service import DocumentStorageService
from app.services.folder_service import FolderService
from app.services.organization_service import OrganizationService
from app.services.storage_quota_service import StorageQuotaService
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_sync_service import CloudSyncService

logger = logging.getLogger(__name__)


class DocumentService:
    """Regras documentais sobre a API do DocumentRepository."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        storage_service: DocumentStorageService | None = None,
    ):
        self.database = Database(db_name=db_path)
        self.document_repository = DocumentRepository(database=self.database)
        self.organization_service = OrganizationService(self.database)
        self.folder_service = FolderService(self.database)
        self.cloud_manager = CloudManager(self.database)
        self.cloud_sync_service = CloudSyncService(self.database, self.cloud_manager)
        self.storage_service = storage_service or DocumentStorageService(self.database.paths)
        self.storage_quota_service = StorageQuotaService(
            self.database, self.storage_service.paths.storage
        )
        # Histórico básico preexistente é preservado, sem ampliar seu domínio.
        self.history_service = HistoryService(database=self.database)

    @property
    def active_organization_id(self) -> int:
        return self.organization_service.active_id

    def set_active_organization(self, organization_id: int):
        return self.organization_service.set_active(organization_id)

    def import_document(
        self,
        file_path: str,
        folder_id: int | None = None,
        *,
        organization_id: int | None = None,
        title: str | None = None,
        category: str | None = None,
        description: str | None = None,
        tags: str | None = None,
        document_date: str | None = None,
        notes: str | None = None,
        source_type: str = "IMPORT",
        sync_cloud: bool = True,
    ) -> DocumentModel:
        path = self._validated_path(file_path)
        extension = path.suffix.lower()
        checksum = self._calculate_checksum(path)
        organization_id = organization_id or self.active_organization_id
        source_type = source_type.strip().upper()
        allowed_sources = {
            "IMPORT", "SCANNER", "CONVERTER", "PDF_TOOLS", "DIGITAL_SIGNATURE",
            "HANDWRITTEN_SIGNATURE", "CLOUD_DOWNLOAD",
        }
        if source_type not in allowed_sources:
            raise InvalidDocumentError("Origem documental inválida.")
        if folder_id is not None:
            folder = self.folder_service.repository.find_by_id(folder_id, organization_id)
            if folder is None or folder.status != "ACTIVE":
                raise InvalidDocumentError("A pasta selecionada não pertence à organização ativa.")
        if self.document_repository.exists_checksum(checksum, organization_id):
            raise DuplicateDocumentError("Este documento já foi importado.")

        operation_id = self.storage_quota_service.reserve(
            organization_id, path.stat().st_size, str(uuid4())
        )
        stored = None
        committed = False
        now = self._now()
        try:
            stored = self.storage_service.store(path, checksum)
            with self.database.transaction():
                document_name = (title or path.name).strip() or path.name
                if not Path(document_name).suffix:
                    document_name += extension
                entity = DocumentEntity(
                    organization_id=organization_id,
                    folder_id=folder_id,
                    name=document_name,
                    original_name=path.name,
                    path=stored.storage_path,
                    source_path=str(path),
                    storage_path=stored.storage_path,
                    internal_name=stored.internal_name,
                    managed=True,
                    extension=extension,
                    file_type=self._classify_file_type(extension),
                    size=stored.size,
                    checksum=checksum,
                    category=category or self._classify_category(extension),
                    description=description or None,
                    favorite=False,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=None,
                    source_type=source_type,
                    tags=tags or None,
                    document_date=document_date or None,
                    notes=notes or None,
                )
                created = self.document_repository.create(entity)
                action = "SCAN" if source_type == "SCANNER" else "IMPORT"
                self._record_history(created.id, action, f"Documento adicionado: {document_name}")
                self.storage_quota_service.commit_reservation(operation_id)
            committed = True
            logger.info("Documento importado id=%s", created.id)
            if sync_cloud:
                try:
                    self.cloud_sync_service.enqueue_upload(created.id, organization_id)
                except Exception:
                    logger.exception("Documento salvo localmente, mas a sincronização não foi enfileirada")
            refreshed = self.document_repository.find_by_id(created.id, organization_id)
            return DocumentModel.from_entity(refreshed or created)
        except Exception:
            if not committed:
                self.storage_quota_service.release_reservation(operation_id)
            try:
                if stored is not None and not committed:
                    self.storage_service.remove(stored.storage_path)
            except StorageError:
                logger.exception("Falha ao remover arquivo após rollback da importação")
            raise

    def get_document(self, document_id: int) -> Optional[DocumentModel]:
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        return DocumentModel.from_entity(entity) if entity else None

    def list_documents(self, folder_id: int | None = None) -> list[DocumentModel]:
        return self._models(self.document_repository.find_all(self.active_organization_id, folder_id))

    def search_documents(
        self,
        term: str,
        file_type: str | None = None,
        folder_id: int | None = None,
    ) -> list[DocumentModel]:
        if not term.strip():
            return self.filter_by_type(file_type or "Todos", folder_id)
        return self._models(
            self.document_repository.search(
                term, file_type, self.active_organization_id, folder_id
            )
        )

    def filter_by_type(self, file_type: str, folder_id: int | None = None) -> list[DocumentModel]:
        if not file_type or file_type.lower() == "todos":
            return self.list_documents(folder_id)
        return self._models(
            self.document_repository.find_by_type(
                file_type, self.active_organization_id, folder_id
            )
        )

    def get_recent_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_recent(10, self.active_organization_id))

    def get_favorite_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_favorites(self.active_organization_id))

    def get_trashed_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_trashed(self.active_organization_id))

    def toggle_favorite(self, document_id: int) -> DocumentModel:
        updated = self.document_repository.toggle_favorite(document_id, self.active_organization_id)
        if updated is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(updated.id, "FAVORITE", f"Favorito atualizado: {updated.name}")
        return DocumentModel.from_entity(updated)

    def delete_document(self, document_id: int) -> bool:
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None:
            return False
        changed = self.document_repository.soft_delete(document_id, self.active_organization_id)
        if changed:
            self._record_history(document_id, "DELETE", f"Documento movido para lixeira: {entity.name}")
        return changed

    def restore_document(self, document_id: int) -> DocumentModel:
        if not self.document_repository.restore(document_id, self.active_organization_id):
            raise InvalidDocumentError("Documento não encontrado.")
        restored = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if restored is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(document_id, "RESTORE", f"Documento restaurado: {restored.name}")
        return DocumentModel.from_entity(restored)

    def copy_document(self, document_id: int, folder_id: int | None = None) -> DocumentModel:
        source=self.document_repository.find_by_id(document_id,self.active_organization_id)
        if source is None: raise InvalidDocumentError("Documento não encontrado.")
        path=Path(source.storage_path or source.path).expanduser().resolve()
        if not path.is_file(): raise InvalidDocumentError("Arquivo do documento não encontrado.")
        operation_id=self.storage_quota_service.reserve(self.active_organization_id,source.size,str(uuid4()))
        stored=None
        committed=False
        now=self._now()
        try:
            stored=self.storage_service.store(path,source.checksum)
            entity=replace(source,id=None,folder_id=folder_id,name=f"Cópia de {source.name}",path=stored.storage_path,storage_path=stored.storage_path,internal_name=stored.internal_name,status="ACTIVE",favorite=False,created_at=now,updated_at=now,last_accessed_at=None,cloud_status="LOCAL_ONLY",cloud_provider=None,remote_id=None,remote_version=None,last_synced_at=None)
            with self.database.transaction():
                created=self.document_repository.create(entity)
                self._record_history(created.id,"COPY",f"Cópia criada de {source.name}")
                self.storage_quota_service.commit_reservation(operation_id)
            committed=True
            try:self.cloud_sync_service.enqueue_upload(created.id,self.active_organization_id)
            except Exception:logger.exception("Cópia local criada, mas a sincronização não foi enfileirada")
            return DocumentModel.from_entity(created)
        except Exception:
            if not committed:self.storage_quota_service.release_reservation(operation_id)
            if stored is not None and not committed:self.storage_service.remove(stored.storage_path)
            raise

    def open_document(self, document_id: int) -> DocumentModel:
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None:
            raise InvalidDocumentError("Documento não encontrado.")
        if entity.status != "ACTIVE":
            raise InvalidDocumentError("O documento está na lixeira.")
        if entity.managed:
            if not entity.storage_path or not self.storage_service.exists(entity.storage_path):
                raise InvalidDocumentError("O arquivo interno do documento não foi encontrado.")
            path = Path(entity.storage_path)
        else:
            path = Path(entity.path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise InvalidDocumentError("O arquivo não existe mais no caminho registrado.")
        entity.last_accessed_at = self._now()
        entity.updated_at = entity.last_accessed_at
        updated = self.document_repository.update(entity)
        self._record_history(entity.id, "OPEN", f"Documento aberto: {entity.name}")
        return DocumentModel.from_entity(updated)

    def permanently_delete_document(self, document_id: int) -> bool:
        """Remove registro e arquivo gerenciado; ainda não exposto pela interface."""
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None or entity.status != "TRASHED":
            return False
        quarantine: Path | None = None
        original_storage: Path | None = None
        if entity.managed and entity.storage_path:
            original_storage = Path(entity.storage_path).resolve()
            if not self.storage_service.is_managed_path(original_storage):
                raise StorageError("Caminho interno inválido para exclusão permanente.")
            if original_storage.exists():
                quarantine = self.storage_service.create_temp_path(original_storage.suffix)
                original_storage.replace(quarantine)
        try:
            with self.database.transaction():
                self._record_history(
                    document_id,
                    "PERMANENT_DELETE",
                    f"Documento excluído permanentemente: {entity.name}",
                )
                deleted = self.document_repository.hard_delete(document_id, self.active_organization_id)
                if deleted and entity.managed:
                    self.storage_quota_service.release_used(entity.organization_id, entity.size)
            if quarantine and quarantine.exists():
                quarantine.unlink()
            return deleted
        except Exception:
            if quarantine and quarantine.exists() and original_storage:
                original_storage.parent.mkdir(parents=True, exist_ok=True)
                quarantine.replace(original_storage)
            raise

    def empty_trash(self) -> int:
        documents = self.document_repository.find_trashed(self.active_organization_id)
        count = 0
        for document in documents:
            if self.permanently_delete_document(document.id):
                count += 1
        return count

    def get_storage_usage(self):
        return self.storage_quota_service.get_usage_summary(self.active_organization_id)

    def recalculate_storage_usage(self):
        return self.storage_quota_service.recalculate_usage(self.active_organization_id)

    def get_largest_documents(self, limit: int = 10) -> list[DocumentModel]:
        return self._models(
            self.document_repository.find_largest(self.active_organization_id, limit)
        )

    def move_document(self, document_id: int, folder_id: int | None) -> DocumentModel:
        if folder_id is not None:
            folder = self.folder_service.repository.find_by_id(folder_id, self.active_organization_id)
            if folder is None or folder.status != "ACTIVE":
                raise InvalidDocumentError("Pasta inválida para a organização ativa.")
        if not self.document_repository.move_to_folder(
            document_id, self.active_organization_id, folder_id
        ):
            raise InvalidDocumentError("Documento não encontrado na organização ativa.")
        document = self.get_document(document_id)
        if document is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(document_id, "MOVE", "Documento movido para outra pasta lógica")
        try:
            self.cloud_sync_service.enqueue_move(document_id, self.active_organization_id)
        except Exception:
            logger.exception("Movimento local concluído, mas não foi enfileirado na nuvem")
        return document

    def delete_folder(self, folder_id: int) -> bool:
        affected = self.document_repository.find_in_folder_tree(
            self.active_organization_id, folder_id
        )
        changed = self.folder_service.delete(self.active_organization_id, folder_id)
        if changed:
            self.document_repository.clear_deleted_folders(self.active_organization_id)
            for document in affected:
                try:
                    self.cloud_sync_service.enqueue_move(
                        document.id, self.active_organization_id
                    )
                except Exception:
                    logger.exception(
                        "Pasta removida localmente, mas movimento remoto não foi enfileirado"
                    )
        return changed

    def _record_history(self, document_id: Optional[int], action: str, description: str) -> None:
        self.history_service.record_action(document_id, action, description)

    @staticmethod
    def _validated_path(file_path: str) -> Path:
        try:
            path = Path(file_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise InvalidDocumentError("O arquivo informado não existe.") from exc
        if not path.is_file():
            raise InvalidDocumentError("O caminho informado não é um arquivo regular.")
        return path

    @staticmethod
    def _models(entities: list[DocumentEntity]) -> list[DocumentModel]:
        return [DocumentModel.from_entity(entity) for entity in entities]

    @staticmethod
    def _calculate_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _classify_file_type(extension: str) -> str:
        if extension == ".pdf":
            return "PDF"
        if extension in {".doc", ".docx"}:
            return "DOCX"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "SPREADSHEET"
        if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
            return "IMAGE"
        if extension in {".txt", ".md", ".rtf"}:
            return "TEXT"
        return "OTHER"

    @staticmethod
    def _classify_category(extension: str) -> str:
        if extension in {".pdf", ".doc", ".docx"}:
            return "Documento"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "Planilha"
        if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
            return "Imagem"
        if extension in {".txt", ".md", ".rtf"}:
            return "Texto"
        return "Arquivo"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
