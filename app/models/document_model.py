from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.entities.document_entity import DocumentEntity


@dataclass
class DocumentModel:
    id: Optional[int] = None
    name: str = ""
    original_name: Optional[str] = None
    path: str = ""
    file_type: Optional[str] = None
    extension: Optional[str] = None
    size: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    description: Optional[str] = None
    favorite: bool = False
    checksum: Optional[str] = None
    status: str = "ACTIVE"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_accessed_at: Optional[str] = None

    @classmethod
    def from_entity(cls, entity: DocumentEntity) -> "DocumentModel":
        return cls(
            id=entity.id,
            name=entity.name,
            original_name=entity.original_name,
            path=entity.path,
            file_type=entity.file_type,
            extension=entity.extension,
            size=entity.size,
            category=entity.category,
            tags=None,
            description=entity.description,
            favorite=bool(entity.favorite),
            checksum=entity.checksum,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_accessed_at=entity.last_accessed_at,
        )

    def to_entity(self) -> DocumentEntity:
        return DocumentEntity(
            id=self.id,
            name=self.name,
            original_name=self.original_name or "",
            path=self.path,
            file_type=self.file_type or "",
            extension=self.extension or "",
            size=self.size or 0,
            category=self.category,
            description=self.description,
            favorite=int(self.favorite),
            checksum=self.checksum or "",
            status=self.status,
            created_at=self.created_at or "",
            updated_at=self.updated_at or "",
            last_accessed_at=self.last_accessed_at,
        )
