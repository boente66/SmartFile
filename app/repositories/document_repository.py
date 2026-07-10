from __future__ import annotations

from typing import Optional

from app.database.database import Database
from app.entities.document_entity import DocumentEntity



class DocumentRepository(Database):
    def __init__(self, db_path: Optional[str] = None):
        super().__init__(db_name=db_path)

    def create(self, entity: DocumentEntity) -> DocumentEntity:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO documents (
                    name, original_name, path, file_type, extension, size, category,
                    tags, favorite, checksum, created_at, updated_at, last_accessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity.name,
                    entity.original_name,
                    entity.path,
                    entity.file_type,
                    entity.extension,
                    entity.size,
                    entity.category,
                    entity.tags,
                    entity.favorite,
                    entity.checksum,
                    entity.created_at,
                    entity.updated_at,
                    entity.last_accessed_at,
                ),
            )
            connection.commit()
            entity.id = cursor.lastrowid
            return entity

    def update(self, entity: DocumentEntity) -> DocumentEntity:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE documents
                SET name = ?, original_name = ?, path = ?, file_type = ?, extension = ?, size = ?,
                    category = ?, tags = ?, favorite = ?, checksum = ?, created_at = ?,
                    updated_at = ?, last_accessed_at = ?
                WHERE id = ?
                """,
                (
                    entity.name,
                    entity.original_name,
                    entity.path,
                    entity.file_type,
                    entity.extension,
                    entity.size,
                    entity.category,
                    entity.tags,
                    entity.favorite,
                    entity.checksum,
                    entity.created_at,
                    entity.updated_at,
                    entity.last_accessed_at,
                    entity.id,
                ),
            )
            connection.commit()
            return entity

    def delete(self, document_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            connection.commit()
            return cursor.rowcount > 0

    def find_by_id(self, document_id: int) -> Optional[DocumentEntity]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()
            return self._row_to_entity(row) if row else None

    def find_all(self) -> list[DocumentEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def search(self, term: str) -> list[DocumentEntity]:
        pattern = f"%{term.lower()}%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM documents
                WHERE lower(name) LIKE ?
                   OR lower(original_name) LIKE ?
                   OR lower(path) LIKE ?
                   OR lower(tags) LIKE ?
                   OR lower(category) LIKE ?
                ORDER BY created_at DESC, id DESC
                """,
                (pattern, pattern, pattern, pattern, pattern),
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def find_by_type(self, file_type: str) -> list[DocumentEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE file_type = ? ORDER BY created_at DESC, id DESC",
                (file_type,),
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def find_recent(self) -> list[DocumentEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents ORDER BY last_accessed_at DESC, updated_at DESC, created_at DESC LIMIT 10"
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def find_favorites(self) -> list[DocumentEntity]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE favorite = 1 ORDER BY created_at DESC, id DESC"
            ).fetchall()
            return [self._row_to_entity(row) for row in rows]

    def find_by_path(self, path: str) -> Optional[DocumentEntity]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM documents WHERE path = ?",
                (path,),
            ).fetchone()
            return self._row_to_entity(row) if row else None

    def _row_to_entity(self, row) -> DocumentEntity:
        return DocumentEntity(
            id=row["id"],
            name=row["name"],
            original_name=row["original_name"],
            path=row["path"],
            file_type=row["file_type"],
            extension=row["extension"],
            size=row["size"],
            category=row["category"],
            tags=row["tags"],
            favorite=int(row["favorite"] or 0),
            checksum=row["checksum"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
        )
