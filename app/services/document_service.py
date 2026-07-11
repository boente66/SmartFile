from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.entities.document_entity import DocumentEntity
from app.models.document_model import DocumentModel
from app.repositories.document_repository import DocumentRepository
from app.services.history_service import HistoryService


class DocumentService:
    def __init__(self, db_path: Optional[str] = None):
        self.document_repository = DocumentRepository(db_path)
        self.history_service = HistoryService(db_path)

    def import_document(self, file_path: str) -> DocumentModel:
        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"O arquivo não existe: {path}")
        if not path.is_file():
            raise ValueError("O caminho informado não é um arquivo válido.")

        existing = self.document_repository.find_by_path(str(path))
        if existing is not None:
            raise ValueError("Este documento já foi importado.")

        now = self._now()
        checksum = self._calculate_checksum(path)
        entity = DocumentEntity(
            name=path.name,
            original_name=path.name,
            path=str(path),
            file_type=self._classify_file_type(path.suffix.lower()),
            extension=path.suffix.lower(),
            size=path.stat().st_size,
            category=self._classify_category(path.suffix.lower()),
            tags="",
            favorite=0,
            checksum=checksum,
            created_at=now,
            updated_at=now,
            last_accessed_at=now,
        )

        created = self.document_repository.create(entity)
        self._record_history(created.id, "import", f"Documento importado: {path.name}")
        return DocumentModel.from_entity(created)

    def list_documents(self) -> list[DocumentModel]:
        entities = self.document_repository.find_all()
        return [DocumentModel.from_entity(entity) for entity in entities]

    def search_documents(self, term: str) -> list[DocumentModel]:
        if not term.strip():
            return self.list_documents()
        entities = self.document_repository.search(term.strip())
        return [DocumentModel.from_entity(entity) for entity in entities]

    def filter_by_type(self, file_type: str) -> list[DocumentModel]:
        if not file_type or file_type.lower() == "todos":
            return self.list_documents()
        entities = self.document_repository.find_by_type(file_type)
        return [DocumentModel.from_entity(entity) for entity in entities]

    def get_recent_documents(self) -> list[DocumentModel]:
        entities = self.document_repository.find_recent()
        return [DocumentModel.from_entity(entity) for entity in entities]

    def get_document(self, document_id: int) -> Optional[DocumentModel]:
        entity = self.document_repository.find_by_id(document_id)
        return DocumentModel.from_entity(entity) if entity else None

    def toggle_favorite(self, document_id: int) -> DocumentModel:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            raise ValueError("Documento não encontrado.")

        entity.favorite = 0 if entity.favorite else 1
        entity.updated_at = self._now()
        updated = self.document_repository.update(entity)
        action = "favorite_on" if updated.favorite else "favorite_off"
        description = f"Documento marcado como favorito: {updated.name}" if updated.favorite else f"Documento desmarcado como favorito: {updated.name}"
        self._record_history(updated.id, action, description)
        return DocumentModel.from_entity(updated)

    def delete_document(self, document_id: int) -> bool:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            return False

        deleted = self.document_repository.delete(document_id)
        if deleted:
            self._record_history(document_id, "delete", f"Documento removido do registro: {entity.name}")
        return deleted

    def open_document(self, document_id: int) -> DocumentModel:
        entity = self.document_repository.find_by_id(document_id)
        if entity is None:
            raise ValueError("Documento não encontrado.")

        path = Path(entity.path).expanduser()
        if not path.exists():
            raise FileNotFoundError("O arquivo não existe mais no caminho registrado.")

        entity.last_accessed_at = self._now()
        entity.updated_at = self._now()
        self.document_repository.update(entity)
        self._record_history(entity.id, "open", f"Documento aberto: {path.name}")
        return DocumentModel.from_entity(entity)

    def _record_history(self, document_id: Optional[int], action: str, description: str) -> None:
        self.history_service.record_action(document_id, action, description)

    def _calculate_checksum(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _classify_file_type(self, extension: str) -> str:
        if extension in {".pdf"}:
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

    def _classify_category(self, extension: str) -> str:
        if extension in {".pdf"}:
            return "Documento"
        if extension in {".doc", ".docx"}:
            return "Documento"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "Planilha"
        if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
            return "Imagem"
        if extension in {".txt", ".md", ".rtf"}:
            return "Texto"
        return "Arquivo"

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
