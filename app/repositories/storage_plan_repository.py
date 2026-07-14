from app.entities.storage_plan_entity import StoragePlanEntity
from app.repositories.base_repository import BaseRepository


class StoragePlanRepository(BaseRepository):
    def find_by_code(self, code: str) -> StoragePlanEntity | None:
        row = self._fetch_one("SELECT * FROM storage_plans WHERE code=?", (code.upper(),))
        return self._entity(row) if row else None

    def find_all(self, active_only: bool = True) -> list[StoragePlanEntity]:
        query = "SELECT * FROM storage_plans"
        if active_only:
            query += " WHERE is_active=1"
        return [self._entity(row) for row in self._fetch_all(query + " ORDER BY quota_bytes")]

    @staticmethod
    def _entity(row) -> StoragePlanEntity:
        return StoragePlanEntity(
            id=row["id"], code=row["code"], name=row["name"],
            quota_bytes=int(row["quota_bytes"]), description=row["description"],
            is_active=bool(row["is_active"]), created_at=row["created_at"], updated_at=row["updated_at"],
        )
