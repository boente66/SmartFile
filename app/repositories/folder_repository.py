from __future__ import annotations

from app.entities.folder_entity import FolderEntity
from app.repositories.base_repository import BaseRepository


class FolderRepository(BaseRepository):
    def create(self, entity: FolderEntity) -> FolderEntity:
        cursor = self._write(
            """
            INSERT INTO folders (
                organization_id, parent_id, name, description, icon, color,
                created_at, updated_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: FolderEntity) -> FolderEntity:
        self._write(
            """
            UPDATE folders SET organization_id = ?, parent_id = ?, name = ?, description = ?,
                icon = ?, color = ?, created_at = ?, updated_at = ?, status = ? WHERE id = ?
            """,
            (*self._values(entity), entity.id),
        )
        return entity

    def delete(self, folder_id: int, organization_id: int, updated_at: str) -> bool:
        return self._write(
            """
            WITH RECURSIVE descendants(id) AS (
                SELECT id FROM folders WHERE id = ? AND organization_id = ?
                UNION ALL SELECT folders.id FROM folders JOIN descendants ON folders.parent_id = descendants.id
            )
            UPDATE folders SET status = 'DELETED', updated_at = ? WHERE id IN descendants
            """,
            (folder_id, organization_id, updated_at),
        ).rowcount != 0

    def find_by_id(self, folder_id: int, organization_id: int | None = None) -> FolderEntity | None:
        query = "SELECT * FROM folders WHERE id = ?"
        params: tuple[object, ...] = (folder_id,)
        if organization_id is not None:
            query += " AND organization_id = ?"
            params += (organization_id,)
        row = self._fetch_one(query, params)
        return self._entity(row) if row else None

    def find_all(self, organization_id: int) -> list[FolderEntity]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                """
                SELECT * FROM folders WHERE organization_id = ? AND status = 'ACTIVE'
                ORDER BY parent_id IS NOT NULL, name
                """,
                (organization_id,),
            )
        ]

    def find_all_including_deleted(self, organization_id: int) -> list[FolderEntity]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                "SELECT * FROM folders WHERE organization_id=? ORDER BY id",
                (organization_id,),
            )
        ]

    @staticmethod
    def _values(entity: FolderEntity) -> tuple[object, ...]:
        return (
            entity.organization_id, entity.parent_id, entity.name, entity.description,
            entity.icon, entity.color, entity.created_at, entity.updated_at, entity.status,
        )

    @staticmethod
    def _entity(row) -> FolderEntity:
        return FolderEntity(
            id=row["id"], organization_id=row["organization_id"], parent_id=row["parent_id"],
            name=row["name"], description=row["description"], icon=row["icon"], color=row["color"],
            created_at=row["created_at"], updated_at=row["updated_at"], status=row["status"],
        )
