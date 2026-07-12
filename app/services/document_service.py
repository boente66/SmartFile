from __future__ import annotations

import hashlib
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
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

logger = logging.getLogger(__name__)


class DocumentService:
    """Regras do domínio documental; não executa SQL diretamente."""

    def __init__(self, db_path: Optional[str] = None):
        self.database = Database(db_name=db_path)
        self.document_repository = DocumentRepository(database=self.database)
        self.history_service = HistoryService(database=self.database)

    def import_document(self, file_path: str) -> DocumentModel:
        source = self._validated_source(file_path)
        checksum = self._calculate_checksum(source)
        if self.document_repository.exists_checksum(checksum):
            raise DuplicateDocumentError("Este documento já foi importado.")

        internal_name = f"{uuid4().hex}{source.suffix.lower()}"
        destination = (self.database.storage_dir / internal_name).resolve()
        self._assert_inside_storage(destination)
        temporary = (self.database.temp_dir / f"{internal_name}.tmp").resolve()
        now = self._now()

        try:
            shutil.copy2(source, temporary)
        except OSError as exc:
            raise StorageError(f"Não foi possível preparar o documento: {exc}") from exc

        moved = False
        try:
            with self.database.transaction():
                entity = DocumentEntity(
                    name=source.name,
                    original_name=source.name,
                    path=str(destination),
                    internal_name=internal_name,
                    file_type=self._classify_file_type(source.suffix.lower()),
                    extension=source.suffix.lower(),
                    size=source.stat().st_size,
                    category=self._classify_category(source.suffix.lower()),
                    tags="",
                    favorite=0,
                    checksum=checksum,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=now,
                )
                created = self.document_repository.create(entity)
                self._record_history(created.id, "IMPORT", f"Documento importado: {source.name}")
                temporary.replace(destination)
                moved = True
            logger.info("Documento importado id=%s", created.id)
            return DocumentModel.from_entity(created)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            if moved and destination.exists():
                destination.unlink()
            logger.exception("Falha ao importar documento")
            raise

    def list_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_all())

    def search_documents(self, term: str) -> list[DocumentModel]:
        if not term.strip():
            return self.list_documents()
        return self._models(self.document_repository.search(term.strip()))

    def filter_by_type(self, file_type: str) -> list[DocumentModel]:
        if not file_type or file_type.lower() == "todos":
            return self.list_documents()
        return self._models(self.document_repository.find_by_type(file_type))

    def get_recent_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_recent())

    def get_favorite_documents(self) -> list[DocumentModel]:
        return self._models(self.document_repository.find_favorites())

    def get_document(self, document_id: int) -> Optional[DocumentModel]:
        entity = self.document_repository.find_by_id(document_id)
        return DocumentModel.from_entity(entity) if entity else None

    def toggle_favorite(self, document_id: int) -> DocumentModel:
        entity = self._required_document(document_id)
        entity.favorite = 0 if entity.favorite else 1
        entity.updated_at = self._now()
        with self.database.transaction():
            updated = self.document_repository.update(entity)
            description = (
                f"Documento marcado como favorito: {updated.name}"
                if updated.favorite
                else f"Documento desmarcado como favorito: {updated.name}"
            )
            self._record_history(updated.id, "FAVORITE", description)
        return DocumentModel.from_entity(updated)

    def delete_document(self, document_id: int) -> bool:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            return False
        now = self._now()
        with self.database.transaction():
            changed = self.document_repository.update_status(document_id, "TRASHED", now)
            if changed:
                self._record_history(document_id, "DELETE", f"Documento movido para lixeira: {entity.name}")
        return changed

    def restore_document(self, document_id: int) -> DocumentModel:
        entity = self._required_document(document_id)
        with self.database.transaction():
            self.document_repository.update_status(document_id, "ACTIVE", self._now())
            self._record_history(document_id, "RESTORE", f"Documento restaurado: {entity.name}")
        restored = self._required_document(document_id)
        return DocumentModel.from_entity(restored)

    def open_document(self, document_id: int) -> DocumentModel:
        entity = self._required_document(document_id)
        if entity.status != "ACTIVE":
            raise InvalidDocumentError("O documento está na lixeira.")
        path = Path(entity.path).expanduser().resolve()
        self._assert_inside_storage(path)
        if not path.exists() or not path.is_file():
            raise StorageError("O arquivo interno do documento não foi encontrado.")
        entity.last_accessed_at = self._now()
        entity.updated_at = entity.last_accessed_at
        with self.database.transaction():
            self.document_repository.update(entity)
            self._record_history(entity.id, "OPEN", f"Documento aberto: {entity.name}")
        return DocumentModel.from_entity(entity)

    def record_conversion(self, document_id: int, description: str) -> None:
        self._required_document(document_id)
        self._record_history(document_id, "CONVERT", description)

    def record_scan(self, document_id: int, description: str) -> None:
        self._required_document(document_id)
        self._record_history(document_id, "SCAN", description)

    def _record_history(self, document_id: Optional[int], action: str, description: str) -> None:
        self.history_service.record_action(document_id, action, description)

    def _validated_source(self, file_path: str) -> Path:
        try:
            path = Path(file_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise InvalidDocumentError("O arquivo informado não existe.") from exc
        if not path.is_file():
            raise InvalidDocumentError("O caminho informado não é um arquivo regular.")
        return path

    def _assert_inside_storage(self, path: Path) -> None:
        storage = self.database.storage_dir.resolve()
        try:
            path.resolve().relative_to(storage)
        except ValueError as exc:
            raise StorageError("Operação recusada fora do armazenamento interno.") from exc

    def _required_document(self, document_id: int) -> DocumentEntity:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            raise InvalidDocumentError("Documento não encontrado.")
        return entity

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
