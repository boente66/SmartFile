from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.entities.document_entity import DocumentEntity


@dataclass
class DocumentModel:
    id: Optional[int] = None
    organization_id: int = 1
    folder_id: Optional[int] = None
    name: str = ""
    original_name: Optional[str] = None
    path: str = ""
    source_path: Optional[str] = None
    storage_path: Optional[str] = None
    internal_name: Optional[str] = None
    managed: bool = False
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
    cloud_status: str = "LOCAL_ONLY"
    cloud_provider: Optional[str] = None
    remote_id: Optional[str] = None
    remote_version: Optional[str] = None
    last_synced_at: Optional[str] = None
    source_type: str = "IMPORT"
    document_date: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_entity(cls, entity: DocumentEntity) -> "DocumentModel":
        return cls(
            id=entity.id,
            organization_id=entity.organization_id,
            folder_id=entity.folder_id,
            name=entity.name,
            original_name=entity.original_name,
            path=entity.path,
            source_path=entity.source_path,
            storage_path=entity.storage_path,
            internal_name=entity.internal_name,
            managed=entity.managed,
            file_type=entity.file_type,
            extension=entity.extension,
            size=entity.size,
            category=entity.category,
            tags=entity.tags,
            description=entity.description,
            favorite=bool(entity.favorite),
            checksum=entity.checksum,
            status=entity.status,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            last_accessed_at=entity.last_accessed_at,
            cloud_status=entity.cloud_status,
            cloud_provider=entity.cloud_provider,
            remote_id=entity.remote_id,
            remote_version=entity.remote_version,
            last_synced_at=entity.last_synced_at,
            source_type=entity.source_type,
            document_date=entity.document_date,
            notes=entity.notes,
        )

    def to_entity(self) -> DocumentEntity:
        return DocumentEntity(
            id=self.id,
            organization_id=self.organization_id,
            folder_id=self.folder_id,
            name=self.name,
            original_name=self.original_name or "",
            path=self.path,
            source_path=self.source_path,
            storage_path=self.storage_path,
            internal_name=self.internal_name,
            managed=self.managed,
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
            cloud_status=self.cloud_status,
            cloud_provider=self.cloud_provider,
            remote_id=self.remote_id,
            remote_version=self.remote_version,
            last_synced_at=self.last_synced_at,
            source_type=self.source_type,
            tags=self.tags,
            document_date=self.document_date,
            notes=self.notes,
        )
