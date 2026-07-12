from __future__ import annotations

from typing import Optional

from app.database.database import Database
from app.entities.document_entity import DocumentEntity
from app.repositories.base_repository import BaseRepository


class DocumentRepository(BaseRepository):
    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        database: Database | None = None,
    ) -> None:
        super().__init__(db_path, database=database)

    def create(self, entity: DocumentEntity) -> DocumentEntity:
        cursor = self._write(
            """
            INSERT INTO documents (
                name, original_name, path, internal_name, file_type, extension,
                size, category, category_id, tags, favorite, checksum, status,
                created_at, updated_at, last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._entity_values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: DocumentEntity) -> DocumentEntity:
        self._write(
            """
            UPDATE documents SET
                name = ?, original_name = ?, path = ?, internal_name = ?,
                file_type = ?, extension = ?, size = ?, category = ?,
                category_id = ?, tags = ?, favorite = ?, checksum = ?, status = ?,
                created_at = ?, updated_at = ?, last_accessed_at = ?
            WHERE id = ?
            """,
            (*self._entity_values(entity), entity.id),
        )
        return entity

    def delete(self, document_id: int) -> bool:
        return self._write("DELETE FROM documents WHERE id = ?", (document_id,)).rowcount > 0

    def find_by_id(self, document_id: int) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
        return self._row_to_entity(row) if row else None

    def find_all(self) -> list[DocumentEntity]:
        return self._entities(
            "SELECT * FROM documents WHERE status = 'ACTIVE' ORDER BY created_at DESC, id DESC"
        )

    def search(self, term: str) -> list[DocumentEntity]:
        pattern = f"%{term.lower()}%"
        return self._entities(
            """
            SELECT * FROM documents
            WHERE status = 'ACTIVE' AND (
                lower(name) LIKE ? OR lower(original_name) LIKE ?
                OR lower(path) LIKE ? OR lower(tags) LIKE ?
                OR lower(category) LIKE ? OR lower(file_type) LIKE ?
                OR lower(checksum) LIKE ?
            ) ORDER BY created_at DESC, id DESC
            """,
            (pattern,) * 7,
        )

    def find_recent(self, limit: int = 10) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents WHERE status = 'ACTIVE'
            ORDER BY last_accessed_at DESC, updated_at DESC, created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def find_favorites(self) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents
            WHERE status = 'ACTIVE' AND favorite = 1
            ORDER BY created_at DESC, id DESC
            """
        )

    def find_by_category(self, category: int | str) -> list[DocumentEntity]:
        if isinstance(category, int):
            query, params = (
                "SELECT * FROM documents WHERE status = 'ACTIVE' AND category_id = ? ORDER BY created_at DESC",
                (category,),
            )
        else:
            query, params = (
                "SELECT * FROM documents WHERE status = 'ACTIVE' AND lower(category) = lower(?) ORDER BY created_at DESC",
                (category,),
            )
        return self._entities(query, params)

    def exists_checksum(self, checksum: str) -> bool:
        return self._fetch_one(
            "SELECT 1 FROM documents WHERE checksum = ? LIMIT 1", (checksum,)
        ) is not None

    def find_by_checksum(self, checksum: str) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE checksum = ? LIMIT 1", (checksum,))
        return self._row_to_entity(row) if row else None

    def find_by_type(self, file_type: str) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents
            WHERE status = 'ACTIVE' AND file_type = ?
            ORDER BY created_at DESC, id DESC
            """,
            (file_type,),
        )

    def find_by_path(self, path: str) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE path = ?", (path,))
        return self._row_to_entity(row) if row else None

    def update_status(self, document_id: int, status: str, updated_at: str) -> bool:
        if status not in {"ACTIVE", "TRASHED"}:
            raise ValueError(f"Status documental inválido: {status}")
        return self._write(
            "UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
            (status, updated_at, document_id),
        ).rowcount > 0

    def _entities(self, query: str, params=()) -> list[DocumentEntity]:
        return [self._row_to_entity(row) for row in self._fetch_all(query, params)]

    @staticmethod
    def _entity_values(entity: DocumentEntity) -> tuple[object, ...]:
        return (
            entity.name, entity.original_name, entity.path, entity.internal_name,
            entity.file_type, entity.extension, entity.size, entity.category,
            entity.category_id, entity.tags, entity.favorite, entity.checksum,
            entity.status, entity.created_at, entity.updated_at, entity.last_accessed_at,
        )

    @staticmethod
    def _row_to_entity(row) -> DocumentEntity:
        return DocumentEntity(
            id=row["id"], name=row["name"], original_name=row["original_name"],
            path=row["path"], internal_name=row["internal_name"],
            file_type=row["file_type"], extension=row["extension"], size=row["size"],
            category=row["category"], category_id=row["category_id"], tags=row["tags"],
            favorite=int(row["favorite"] or 0), checksum=row["checksum"],
            status=row["status"] or "ACTIVE", created_at=row["created_at"],
            updated_at=row["updated_at"], last_accessed_at=row["last_accessed_at"],
        )
