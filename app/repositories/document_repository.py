from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.database.database import Database
from app.entities.document_entity import DocumentEntity
from app.repositories.base_repository import BaseRepository


class DocumentRepository(BaseRepository):
    """Única camada autorizada a executar SQL sobre documents."""

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
                name, original_name, path, extension, file_type, size, checksum,
                category, description, favorite, status, created_at, updated_at,
                last_accessed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: DocumentEntity) -> DocumentEntity:
        self._write(
            """
            UPDATE documents SET
                name = ?, original_name = ?, path = ?, extension = ?,
                file_type = ?, size = ?, checksum = ?, category = ?,
                description = ?, favorite = ?, status = ?, created_at = ?,
                updated_at = ?, last_accessed_at = ?
            WHERE id = ?
            """,
            (*self._values(entity), entity.id),
        )
        return entity

    def delete(self, document_id: int) -> bool:
        """Compatibilidade: exclusão pública é lógica."""
        return self.soft_delete(document_id)

    def find_by_id(self, document_id: int) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE id = ?", (document_id,))
        return self._row_to_entity(row) if row else None

    def find_all(self) -> list[DocumentEntity]:
        return self._entities(
            "SELECT * FROM documents WHERE status = 'ACTIVE' ORDER BY created_at DESC, id DESC"
        )

    def search(self, term: str, file_type: str | None = None) -> list[DocumentEntity]:
        pattern = f"%{term.strip().lower()}%"
        query = """
            SELECT * FROM documents
            WHERE status = 'ACTIVE'
              AND (lower(name) LIKE ? OR lower(original_name) LIKE ?
                   OR lower(category) LIKE ? OR lower(description) LIKE ?)
        """
        params: list[object] = [pattern, pattern, pattern, pattern]
        if file_type and file_type.lower() != "todos":
            query += " AND file_type = ?"
            params.append(file_type)
        query += " ORDER BY created_at DESC, id DESC"
        return self._entities(query, params)

    def find_by_type(self, file_type: str) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents WHERE status = 'ACTIVE' AND file_type = ?
            ORDER BY created_at DESC, id DESC
            """,
            (file_type,),
        )

    def find_recent(self, limit: int = 10) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents WHERE status = 'ACTIVE'
            ORDER BY last_accessed_at DESC, updated_at DESC, created_at DESC LIMIT ?
            """,
            (limit,),
        )

    def find_favorites(self) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents WHERE status = 'ACTIVE' AND favorite = 1
            ORDER BY created_at DESC, id DESC
            """
        )

    def exists_checksum(self, checksum: str) -> bool:
        return self._fetch_one(
            "SELECT 1 FROM documents WHERE checksum = ? LIMIT 1", (checksum,)
        ) is not None

    def find_by_path(self, path: str) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE path = ?", (path,))
        return self._row_to_entity(row) if row else None

    def toggle_favorite(self, document_id: int) -> Optional[DocumentEntity]:
        now = self._now()
        self._write(
            """
            UPDATE documents
            SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END, updated_at = ?
            WHERE id = ?
            """,
            (now, document_id),
        )
        return self.find_by_id(document_id)

    def soft_delete(self, document_id: int) -> bool:
        return self._write(
            "UPDATE documents SET status = 'TRASHED', updated_at = ? WHERE id = ?",
            (self._now(), document_id),
        ).rowcount > 0

    def restore(self, document_id: int) -> bool:
        return self._write(
            "UPDATE documents SET status = 'ACTIVE', updated_at = ? WHERE id = ?",
            (self._now(), document_id),
        ).rowcount > 0

    def _entities(self, query: str, params=()) -> list[DocumentEntity]:
        return [self._row_to_entity(row) for row in self._fetch_all(query, params)]

    @staticmethod
    def _values(entity: DocumentEntity) -> tuple[object, ...]:
        return (
            entity.name, entity.original_name, entity.path, entity.extension,
            entity.file_type, entity.size, entity.checksum, entity.category,
            entity.description, int(entity.favorite), entity.status,
            entity.created_at, entity.updated_at, entity.last_accessed_at,
        )

    @staticmethod
    def _row_to_entity(row) -> DocumentEntity:
        return DocumentEntity(
            id=row["id"], name=row["name"], original_name=row["original_name"],
            path=row["path"], extension=row["extension"], file_type=row["file_type"],
            size=int(row["size"] or 0), checksum=row["checksum"],
            category=row["category"], description=row["description"],
            favorite=bool(row["favorite"]), status=row["status"] or "ACTIVE",
            created_at=row["created_at"], updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
