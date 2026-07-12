from __future__ import annotations

from typing import Optional

from app.database.database import Database
from app.entities.history_entity import HistoryEntity
from app.repositories.base_repository import BaseRepository


class HistoryRepository(BaseRepository):
    def __init__(self, db_path: Optional[str] = None, *, database: Database | None = None):
        super().__init__(db_path, database=database)

    def create(self, entity: HistoryEntity) -> HistoryEntity:
        cursor = self._write(
            "INSERT INTO history (document_id, action, description, created_at) VALUES (?, ?, ?, ?)",
            (entity.document_id, entity.action, entity.description, entity.created_at),
        )
        entity.id = cursor.lastrowid
        return entity

    def find_by_document_id(self, document_id: int) -> list[HistoryEntity]:
        rows = self._fetch_all(
            "SELECT * FROM history WHERE document_id = ? ORDER BY created_at DESC, id DESC",
            (document_id,),
        )
        return [self._row_to_entity(row) for row in rows]

    def find_recent(self, limit: int = 10) -> list[HistoryEntity]:
        rows = self._fetch_all(
            "SELECT * FROM history ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )
        return [self._row_to_entity(row) for row in rows]

    @staticmethod
    def _row_to_entity(row) -> HistoryEntity:
        return HistoryEntity(
            id=row["id"], document_id=row["document_id"], action=row["action"],
            description=row["description"], created_at=row["created_at"],
        )
