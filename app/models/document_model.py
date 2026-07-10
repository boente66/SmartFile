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
    favorite: bool = False
    checksum: Optional[str] = None
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
            tags=entity.tags,
            favorite=bool(entity.favorite),
            checksum=entity.checksum,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_accessed_at=entity.last_accessed_at,
        )

    def to_entity(self) -> DocumentEntity:
        return DocumentEntity(
            id=self.id,
            name=self.name,
            original_name=self.original_name,
            path=self.path,
            file_type=self.file_type,
            extension=self.extension,
            size=self.size,
            category=self.category,
            tags=self.tags,
            favorite=int(self.favorite),
            checksum=self.checksum,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_accessed_at=self.last_accessed_at,
        )
