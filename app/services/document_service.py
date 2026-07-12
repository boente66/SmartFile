from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
        self.storage_service = storage_service or DocumentStorageService(self.database.paths)
        # Histórico básico preexistente é preservado, sem ampliar seu domínio.
        self.history_service = HistoryService(database=self.database)

    def import_document(self, file_path: str) -> DocumentModel:
        path = self._validated_path(file_path)
        extension = path.suffix.lower()
        checksum = self._calculate_checksum(path)
        if self.document_repository.exists_checksum(checksum):
            raise DuplicateDocumentError("Este documento já foi importado.")

        stored = self.storage_service.store(path, checksum)
        now = self._now()
        try:
            with self.database.transaction():
                entity = DocumentEntity(
                    name=path.name,
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
                    category=self._classify_category(extension),
                    description=None,
                    favorite=False,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=None,
                )
                created = self.document_repository.create(entity)
                self._record_history(created.id, "IMPORT", f"Documento importado: {path.name}")
            logger.info("Documento importado id=%s", created.id)
            return DocumentModel.from_entity(created)
        except Exception:
            try:
                self.storage_service.remove(stored.storage_path)
            except StorageError:
                logger.exception("Falha ao remover arquivo após rollback da importação")
            raise

    def get_document(self, document_id: int) -> Optional[DocumentModel]:
        entity = self.document_repository.find_by_id(document_id)
        return DocumentModel.from_entity(entity) if entity else None

    def list_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_all())

    def search_documents(
        self,
        term: str,
        file_type: str | None = None,
    ) -> list[DocumentModel]:
        if not term.strip():
            return self.filter_by_type(file_type or "Todos")
        return self._models(self.document_repository.search(term, file_type))

    def filter_by_type(self, file_type: str) -> list[DocumentModel]:
        if not file_type or file_type.lower() == "todos":
            return self.list_documents()
        return self._models(self.document_repository.find_by_type(file_type))

    def get_recent_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_recent())

    def get_favorite_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_favorites())

    def toggle_favorite(self, document_id: int) -> DocumentModel:
        updated = self.document_repository.toggle_favorite(document_id)
        if updated is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(updated.id, "FAVORITE", f"Favorito atualizado: {updated.name}")
        return DocumentModel.from_entity(updated)

    def delete_document(self, document_id: int) -> bool:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            return False
        changed = self.document_repository.soft_delete(document_id)
        if changed:
            self._record_history(document_id, "DELETE", f"Documento movido para lixeira: {entity.name}")
        return changed

    def restore_document(self, document_id: int) -> DocumentModel:
        if not self.document_repository.restore(document_id):
            raise InvalidDocumentError("Documento não encontrado.")
        restored = self.document_repository.find_by_id(document_id)
        if restored is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(document_id, "RESTORE", f"Documento restaurado: {restored.name}")
        return DocumentModel.from_entity(restored)

    def open_document(self, document_id: int) -> DocumentModel:
        entity = self.document_repository.find_by_id(document_id)
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
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
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
                deleted = self.document_repository.hard_delete(document_id)
            if quarantine and quarantine.exists():
                quarantine.unlink()
            return deleted
        except Exception:
            if quarantine and quarantine.exists() and original_storage:
                original_storage.parent.mkdir(parents=True, exist_ok=True)
                quarantine.replace(original_storage)
            raise

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
