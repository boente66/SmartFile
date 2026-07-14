from app.entities.organization_storage_entity import OrganizationStorageEntity
from app.repositories.base_repository import BaseRepository


class OrganizationStorageRepository(BaseRepository):
    def find_by_organization(self, organization_id: int) -> OrganizationStorageEntity | None:
        row = self._fetch_one("SELECT * FROM organization_storage WHERE organization_id=?", (organization_id,))
        return self._entity(row) if row else None

    def assign_plan(self, organization_id: int, plan_id: int, quota_bytes: int, now: str) -> OrganizationStorageEntity:
        self._write(
            """INSERT INTO organization_storage
               (organization_id, storage_plan_id, quota_bytes, used_bytes, reserved_bytes, created_at, updated_at)
               VALUES (?, ?, ?, 0, 0, ?, ?)
               ON CONFLICT(organization_id) DO UPDATE SET storage_plan_id=excluded.storage_plan_id,
                   quota_bytes=excluded.quota_bytes, updated_at=excluded.updated_at""",
            (organization_id, plan_id, quota_bytes, now, now),
        )
        return self.find_by_organization(organization_id)

    def reserve_if_available(self, organization_id: int, size_bytes: int, now: str) -> bool:
        return self._write(
            """UPDATE organization_storage SET reserved_bytes=reserved_bytes+?, updated_at=?
               WHERE organization_id=? AND ? <= quota_bytes-used_bytes-reserved_bytes""",
            (size_bytes, now, organization_id, size_bytes),
        ).rowcount == 1

    def commit_reserved(self, organization_id: int, size_bytes: int, now: str) -> bool:
        return self._write(
            """UPDATE organization_storage SET reserved_bytes=reserved_bytes-?,
               used_bytes=used_bytes+?, updated_at=?
               WHERE organization_id=? AND reserved_bytes>=?""",
            (size_bytes, size_bytes, now, organization_id, size_bytes),
        ).rowcount == 1

    def release_reserved(self, organization_id: int, size_bytes: int, now: str) -> bool:
        return self._write(
            """UPDATE organization_storage SET reserved_bytes=reserved_bytes-?, updated_at=?
               WHERE organization_id=? AND reserved_bytes>=?""",
            (size_bytes, now, organization_id, size_bytes),
        ).rowcount == 1

    def release_used(self, organization_id: int, size_bytes: int, now: str) -> None:
        self._write(
            """UPDATE organization_storage SET used_bytes=MAX(0, used_bytes-?), updated_at=?
               WHERE organization_id=?""",
            (size_bytes, now, organization_id),
        )

    def set_used(self, organization_id: int, used_bytes: int, now: str) -> None:
        self._write(
            "UPDATE organization_storage SET used_bytes=?, updated_at=? WHERE organization_id=?",
            (max(0, used_bytes), now, organization_id),
        )

    @staticmethod
    def _entity(row) -> OrganizationStorageEntity:
        return OrganizationStorageEntity(
            id=row["id"], organization_id=row["organization_id"], storage_plan_id=row["storage_plan_id"],
            quota_bytes=int(row["quota_bytes"]), used_bytes=int(row["used_bytes"]),
            reserved_bytes=int(row["reserved_bytes"]), created_at=row["created_at"], updated_at=row["updated_at"],
        )
