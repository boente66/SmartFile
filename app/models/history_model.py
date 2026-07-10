from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.entities.history_entity import HistoryEntity


@dataclass
class HistoryModel:
    id: Optional[int] = None
    document_id: Optional[int] = None
    action: str = ""
    description: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_entity(cls, entity: HistoryEntity) -> "HistoryModel":
        return cls(
            id=entity.id,
            document_id=entity.document_id,
            action=entity.action,
            description=entity.description,
            created_at=entity.created_at,
        )

    def to_entity(self) -> HistoryEntity:
        return HistoryEntity(
            id=self.id,
            document_id=self.document_id,
            action=self.action,
            description=self.description,
            created_at=self.created_at,
        )
