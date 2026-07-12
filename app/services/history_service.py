from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.database.database import Database
from app.models.history_model import HistoryModel
from app.repositories.history_repository import HistoryRepository
from app.entities.history_entity import HistoryEntity


class HistoryService:
    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        database: Database | None = None,
    ):
        self.repository = HistoryRepository(db_path, database=database)

    def record_action(self, document_id: Optional[int], action: str, description: str) -> HistoryModel:
        entity = HistoryEntity(
            document_id=document_id,
            action=action.upper(),
            description=description,
            created_at=self._now(),
        )
        created = self.repository.create(entity)
        return HistoryModel.from_entity(created)

    def list_history(self, document_id: Optional[int]) -> list[HistoryModel]:
        if document_id is None:
            return []
        entities = self.repository.find_by_document_id(document_id)
        return [HistoryModel.from_entity(entity) for entity in entities]

    def get_recent_history(self, limit: int = 10) -> list[HistoryModel]:
        entities = self.repository.find_recent(limit)
        return [HistoryModel.from_entity(entity) for entity in entities]

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
