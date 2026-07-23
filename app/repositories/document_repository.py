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
                organization_id, folder_id, name, original_name, path, source_path, storage_path, internal_name,
                managed, extension, file_type, size, checksum,
                category, description, favorite, status, created_at, updated_at,
                last_accessed_at, cloud_status, cloud_provider, remote_id,
                remote_version, last_synced_at, source_type, tags, document_date, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: DocumentEntity) -> DocumentEntity:
        self._write(
            """
            UPDATE documents SET
                organization_id = ?, folder_id = ?, name = ?, original_name = ?, path = ?, source_path = ?,
                storage_path = ?, internal_name = ?, managed = ?, extension = ?,
                file_type = ?, size = ?, checksum = ?, category = ?,
                description = ?, favorite = ?, status = ?, created_at = ?,
                updated_at = ?, last_accessed_at = ?, cloud_status = ?,
                cloud_provider = ?, remote_id = ?, remote_version = ?, last_synced_at = ?,
                source_type = ?, tags = ?, document_date = ?, notes = ?
            WHERE id = ?
            """,
            (*self._values(entity), entity.id),
        )
        return entity

    def delete(self, document_id: int) -> bool:
        """Compatibilidade: exclusão pública é lógica."""
        return self.soft_delete(document_id)

    def hard_delete(self, document_id: int, organization_id: int | None = None) -> bool:
        query = "DELETE FROM documents WHERE id = ?"
        params: tuple[object, ...] = (document_id,)
        if organization_id is not None:
            query += " AND organization_id = ?"
            params += (organization_id,)
        return self._write(query, params).rowcount > 0

    def find_by_id(self, document_id: int, organization_id: int | None = None) -> Optional[DocumentEntity]:
        query = "SELECT * FROM documents WHERE id = ?"
        params: tuple[object, ...] = (document_id,)
        if organization_id is not None:
            query += " AND organization_id = ?"
            params += (organization_id,)
        row = self._fetch_one(query, params)
        return self._row_to_entity(row) if row else None

    def find_all(self, organization_id: int | None = None, folder_id: int | None = None) -> list[DocumentEntity]:
        query = "SELECT * FROM documents WHERE status = 'ACTIVE'"
        params: list[object] = []
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if folder_id is not None:
            query += " AND folder_id = ?"
            params.append(folder_id)
        query += " ORDER BY created_at DESC, id DESC"
        return self._entities(
            query, params
        )

    def search(self, term: str, file_type: str | None = None, organization_id: int | None = None, folder_id: int | None = None) -> list[DocumentEntity]:
        pattern = f"%{term.strip().lower()}%"
        query = """
            SELECT * FROM documents
            WHERE status = 'ACTIVE'
              AND (lower(name) LIKE ? OR lower(original_name) LIKE ?
                   OR lower(category) LIKE ? OR lower(description) LIKE ?
                   OR lower(tags) LIKE ?)
        """
        params: list[object] = [pattern, pattern, pattern, pattern, pattern]
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if folder_id is not None:
            query += " AND folder_id = ?"
            params.append(folder_id)
        if file_type and file_type.lower() != "todos":
            query += " AND file_type = ?"
            params.append(file_type)
        query += " ORDER BY created_at DESC, id DESC"
        return self._entities(query, params)

    def find_by_type(self, file_type: str, organization_id: int | None = None, folder_id: int | None = None) -> list[DocumentEntity]:
        query = "SELECT * FROM documents WHERE status = 'ACTIVE' AND file_type = ?"
        params: list[object] = [file_type]
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        if folder_id is not None:
            query += " AND folder_id = ?"
            params.append(folder_id)
        query += " ORDER BY created_at DESC, id DESC"
        return self._entities(
            query, params,
        )

    def find_recent(self, limit: int = 10, organization_id: int | None = None) -> list[DocumentEntity]:
        query = "SELECT * FROM documents WHERE status = 'ACTIVE'"
        params: list[object] = []
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        query += " ORDER BY last_accessed_at DESC, updated_at DESC, created_at DESC LIMIT ?"
        params.append(limit)
        return self._entities(
            query, params,
        )

    def find_favorites(self, organization_id: int | None = None) -> list[DocumentEntity]:
        query = "SELECT * FROM documents WHERE status = 'ACTIVE' AND favorite = 1"
        params: list[object] = []
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        query += " ORDER BY created_at DESC, id DESC"
        return self._entities(
            query, params
        )

    def find_trashed(self, organization_id: int) -> list[DocumentEntity]:
        return self._entities(
            """
            SELECT * FROM documents WHERE status = 'TRASHED' AND organization_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (organization_id,),
        )

    def exists_checksum(self, checksum: str, organization_id: int | None = None) -> bool:
        query = "SELECT 1 FROM documents WHERE checksum = ?"
        params: list[object] = [checksum]
        if organization_id is not None:
            query += " AND organization_id = ?"
            params.append(organization_id)
        query += " LIMIT 1"
        return self._fetch_one(query, params) is not None

    def find_by_path(self, path: str) -> Optional[DocumentEntity]:
        row = self._fetch_one("SELECT * FROM documents WHERE path = ?", (path,))
        return self._row_to_entity(row) if row else None

    def sum_managed_size(self, organization_id: int) -> int:
        row = self._fetch_one(
            "SELECT COALESCE(SUM(size), 0) AS total FROM documents WHERE organization_id=? AND managed=1",
            (organization_id,),
        )
        return int(row["total"] if row else 0)

    def find_managed_for_usage(self, organization_id: int) -> list[DocumentEntity]:
        return self._entities(
            "SELECT * FROM documents WHERE organization_id=? AND managed=1",
            (organization_id,),
        )

    def find_largest(self, organization_id: int, limit: int = 10) -> list[DocumentEntity]:
        return self._entities(
            "SELECT * FROM documents WHERE organization_id=? ORDER BY size DESC, id DESC LIMIT ?",
            (organization_id, max(1, int(limit))),
        )

    def toggle_favorite(self, document_id: int, organization_id: int | None = None) -> Optional[DocumentEntity]:
        now = self._now()
        self._write(
            """
            UPDATE documents
            SET favorite = CASE favorite WHEN 1 THEN 0 ELSE 1 END, updated_at = ?
            WHERE id = ? AND (? IS NULL OR organization_id = ?)
            """,
            (now, document_id, organization_id, organization_id),
        )
        return self.find_by_id(document_id, organization_id)

    def soft_delete(self, document_id: int, organization_id: int | None = None) -> bool:
        return self._write(
            "UPDATE documents SET status = 'TRASHED', updated_at = ? WHERE id = ? AND (? IS NULL OR organization_id = ?)",
            (self._now(), document_id, organization_id, organization_id),
        ).rowcount > 0

    def restore(self, document_id: int, organization_id: int | None = None) -> bool:
        return self._write(
            "UPDATE documents SET status = 'ACTIVE', updated_at = ? WHERE id = ? AND (? IS NULL OR organization_id = ?)",
            (self._now(), document_id, organization_id, organization_id),
        ).rowcount > 0

    def permanently_delete(self, document_id: int, organization_id: int) -> bool:
        with self.database.transaction():
            self._write("DELETE FROM history WHERE document_id=?",(document_id,))
            return self._write("DELETE FROM documents WHERE id=? AND organization_id=? AND status='TRASHED'",(document_id,organization_id)).rowcount>0

    def empty_trash(self, organization_id: int) -> int:
        rows=self._fetch_all("SELECT id FROM documents WHERE organization_id=? AND status='TRASHED'",(organization_id,))
        with self.database.transaction():
            for row in rows: self._write("DELETE FROM history WHERE document_id=?",(row["id"],))
            self._write("DELETE FROM documents WHERE organization_id=? AND status='TRASHED'",(organization_id,))
        return len(rows)

    def move_to_folder(self, document_id: int, organization_id: int, folder_id: int | None) -> bool:
        return self._write(
            "UPDATE documents SET folder_id = ?, updated_at = ? WHERE id = ? AND organization_id = ?",
            (folder_id, self._now(), document_id, organization_id),
        ).rowcount > 0

    def clear_deleted_folders(self, organization_id: int) -> None:
        self._write(
            """
            UPDATE documents SET folder_id = NULL, updated_at = ?
            WHERE organization_id = ? AND folder_id IN (
                SELECT id FROM folders WHERE organization_id = ? AND status = 'DELETED'
            )
            """,
            (self._now(), organization_id, organization_id),
        )

    def find_in_folder_tree(self, organization_id: int, folder_id: int) -> list[DocumentEntity]:
        return self._entities(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT id FROM folders WHERE id=? AND organization_id=?
                UNION ALL
                SELECT f.id FROM folders f JOIN descendants d ON f.parent_id=d.id
            )
            SELECT d.* FROM documents d
            WHERE d.organization_id=? AND d.folder_id IN descendants
              AND d.status='ACTIVE'
            ORDER BY d.id
            """,
            (folder_id, organization_id, organization_id),
        )

    def update_cloud_state(
        self,
        document_id: int,
        status: str,
        provider: str | None = None,
        remote_id: str | None = None,
        remote_version: str | None = None,
        last_synced_at: str | None = None,
    ) -> bool:
        return self._write(
            """
            UPDATE documents SET cloud_status = ?, cloud_provider = ?, remote_id = ?,
                remote_version = ?, last_synced_at = ?, updated_at = ? WHERE id = ?
            """,
            (status, provider, remote_id, remote_version, last_synced_at, self._now(), document_id),
        ).rowcount > 0

    def _entities(self, query: str, params=()) -> list[DocumentEntity]:
        return [self._row_to_entity(row) for row in self._fetch_all(query, params)]

    @staticmethod
    def _values(entity: DocumentEntity) -> tuple[object, ...]:
        return (
            entity.organization_id, entity.folder_id, entity.name, entity.original_name, entity.path, entity.source_path,
            entity.storage_path, entity.internal_name, int(entity.managed), entity.extension,
            entity.file_type, entity.size, entity.checksum, entity.category,
            entity.description, int(entity.favorite), entity.status,
            entity.created_at, entity.updated_at, entity.last_accessed_at,
            entity.cloud_status, entity.cloud_provider, entity.remote_id,
            entity.remote_version, entity.last_synced_at,
            entity.source_type, entity.tags, entity.document_date, entity.notes,
        )

    @staticmethod
    def _row_to_entity(row) -> DocumentEntity:
        return DocumentEntity(
            id=row["id"], organization_id=int(row["organization_id"] or 0), folder_id=row["folder_id"],
            name=row["name"], original_name=row["original_name"],
            path=row["path"], source_path=row["source_path"],
            storage_path=row["storage_path"], internal_name=row["internal_name"],
            managed=bool(row["managed"]), extension=row["extension"], file_type=row["file_type"],
            size=int(row["size"] or 0), checksum=row["checksum"],
            category=row["category"], description=row["description"],
            favorite=bool(row["favorite"]), status=row["status"] or "ACTIVE",
            created_at=row["created_at"], updated_at=row["updated_at"],
            last_accessed_at=row["last_accessed_at"],
            cloud_status=row["cloud_status"] or "LOCAL_ONLY",
            cloud_provider=row["cloud_provider"], remote_id=row["remote_id"],
            remote_version=row["remote_version"], last_synced_at=row["last_synced_at"],
            source_type=row["source_type"] if "source_type" in row.keys() else "IMPORT",
            tags=row["tags"] if "tags" in row.keys() else None,
            document_date=row["document_date"] if "document_date" in row.keys() else None,
            notes=row["notes"] if "notes" in row.keys() else None,
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
