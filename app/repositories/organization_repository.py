from __future__ import annotations

from app.entities.organization_entity import OrganizationEntity
from app.repositories.base_repository import BaseRepository


class OrganizationRepository(BaseRepository):
    def create(self, entity: OrganizationEntity) -> OrganizationEntity:
        cursor = self._write(
            """
            INSERT INTO organizations (
                name, description, slug, icon, color, created_at, updated_at, is_default, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            self._values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: OrganizationEntity) -> OrganizationEntity:
        self._write(
            """
            UPDATE organizations SET name = ?, description = ?, slug = ?, icon = ?, color = ?,
                created_at = ?, updated_at = ?, is_default = ?, status = ? WHERE id = ?
            """,
            (*self._values(entity), entity.id),
        )
        return entity

    def delete(self, organization_id: int, updated_at: str) -> bool:
        return self._write(
            "UPDATE organizations SET status = 'DELETED', updated_at = ? WHERE id = ? AND is_default = 0",
            (updated_at, organization_id),
        ).rowcount > 0

    def find_by_id(self, organization_id: int) -> OrganizationEntity | None:
        row = self._fetch_one("SELECT * FROM organizations WHERE id = ?", (organization_id,))
        return self._entity(row) if row else None

    def find_by_slug(self, slug: str) -> OrganizationEntity | None:
        row = self._fetch_one("SELECT * FROM organizations WHERE slug = ?", (slug,))
        return self._entity(row) if row else None

    def find_all(self) -> list[OrganizationEntity]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                "SELECT * FROM organizations WHERE status = 'ACTIVE' ORDER BY is_default DESC, name"
            )
        ]

    def find_default(self) -> OrganizationEntity | None:
        row = self._fetch_one(
            """
            SELECT * FROM organizations WHERE status = 'ACTIVE'
            ORDER BY is_default DESC, id LIMIT 1
            """
        )
        return self._entity(row) if row else None

    def get_active_id(self) -> int | None:
        row = self._fetch_one(
            "SELECT value FROM app_settings WHERE key = 'active_organization_id'"
        )
        try:
            return int(row["value"]) if row else None
        except (TypeError, ValueError):
            return None

    def set_active_id(self, organization_id: int) -> None:
        self._write(
            """
            INSERT INTO app_settings (key, value) VALUES ('active_organization_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(organization_id),),
        )

    @staticmethod
    def _values(entity: OrganizationEntity) -> tuple[object, ...]:
        return (
            entity.name, entity.description, entity.slug, entity.icon, entity.color,
            entity.created_at, entity.updated_at, int(entity.is_default), entity.status,
        )

    @staticmethod
    def _entity(row) -> OrganizationEntity:
        return OrganizationEntity(
            id=row["id"], name=row["name"], description=row["description"],
            slug=row["slug"], icon=row["icon"], color=row["color"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            is_default=bool(row["is_default"]), status=row["status"],
        )
