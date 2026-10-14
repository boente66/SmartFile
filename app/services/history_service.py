from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.database.database import Database
from app.models.history_model import HistoryModel
from app.repositories.history_repository import HistoryRepository
from app.entities.history_entity import HistoryEntity
from app.services.audit_service import AuditService
from app.repositories.document_repository import DocumentRepository


class HistoryService:
    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        database: Database | None = None,
        context=None,
    ):
        self.repository = HistoryRepository(db_path, database=database)
        self.audit = AuditService(self.repository.database, context)

    def record_action(self, document_id: Optional[int], action: str, description: str, *, organization_id=None, sha256_before=None, sha256_after=None, details=None) -> HistoryModel:
        entity = HistoryEntity(
            document_id=document_id,
            action=action.upper(),
            description=description,
            created_at=self._now(),
        )
        document = DocumentRepository(database=self.repository.database).find_by_id(document_id) if document_id else None
        organization_id = document.organization_id if document else organization_id
        with self.repository.database.transaction():
            self.audit.record(action, organization_id=organization_id, target_type='document',
                target_id=document_id, document=document, description=description,
                sha256_before=sha256_before, sha256_after=sha256_after, details=details)
            created = self.repository.create(entity)
        return HistoryModel.from_entity(created)

    def list_history(self, document_id: Optional[int]) -> list[HistoryModel]:
        if document_id is None:
            return []
        entities = self.repository.find_by_document_id(document_id)
        return [HistoryModel.from_entity(entity) for entity in entities]

    def get_recent_history(
        self, limit: int = 10, organization_id: int | None = None
    ) -> list[HistoryModel]:
        entities = self.repository.find_recent(limit, organization_id)
        return [HistoryModel.from_entity(entity) for entity in entities]

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
