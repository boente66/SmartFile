from __future__ import annotations

from typing import Optional

from app.database.database import Database
from app.entities.history_entity import HistoryEntity


class HistoryRepository(Database):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__(db_name=db_path)

    def create(self, entity: HistoryEntity) -> HistoryEntity:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO history (document_id, action, description, created_at) VALUES (?, ?, ?, ?)",
                (entity.document_id, entity.action, entity.description, entity.created_at),
            )
            connection.commit()
            entity.id = cursor.lastrowid
            return entity

    def find_by_document_id(self, document_id: int) -> list[HistoryEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM history WHERE document_id = ? ORDER BY created_at DESC, id DESC",
                (document_id,),
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def _row_to_entity(self, row) -> HistoryEntity:
        return HistoryEntity(
            id=row["id"],
            document_id=row["document_id"],
            action=row["action"],
            description=row["description"],
            created_at=row["created_at"],
        )
