from __future__ import annotations

from app.entities.organization_transport_entity import OrganizationTransportEntity
from app.repositories.base_repository import BaseRepository


class OrganizationTransportRepository(BaseRepository):
    def get(self, organization_id: int) -> OrganizationTransportEntity:
        row = self._fetch_one(
            "SELECT * FROM organization_transport_settings WHERE organization_id=?",
            (organization_id,),
        )
        if row is None:
            return OrganizationTransportEntity(organization_id=organization_id)
        return self._entity(row)

    def save(self, entity: OrganizationTransportEntity) -> OrganizationTransportEntity:
        self._write(
            """
            INSERT INTO organization_transport_settings (
                organization_id, mode, endpoint, enabled, verify_tls,
                credential_ref, current_target_id, updated_by_user_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(organization_id) DO UPDATE SET
                mode=excluded.mode, endpoint=excluded.endpoint,
                enabled=excluded.enabled, verify_tls=excluded.verify_tls,
                credential_ref=excluded.credential_ref,
                current_target_id=excluded.current_target_id,
                updated_by_user_id=excluded.updated_by_user_id,
                updated_at=excluded.updated_at
            """,
            (
                entity.organization_id, entity.mode, entity.endpoint,
                int(entity.enabled), int(entity.verify_tls),
                entity.credential_ref, entity.current_target_id,
                entity.updated_by_user_id, entity.updated_at,
            ),
        )
        return self.get(entity.organization_id)

    @staticmethod
    def _entity(row) -> OrganizationTransportEntity:
        return OrganizationTransportEntity(
            organization_id=row["organization_id"], mode=row["mode"],
            endpoint=row["endpoint"], enabled=bool(row["enabled"]),
            verify_tls=bool(row["verify_tls"]),
            credential_ref=(row["credential_ref"] if "credential_ref" in row.keys() else None),
            current_target_id=(
                row["current_target_id"]
                if "current_target_id" in row.keys() else None
            ),
            updated_by_user_id=row["updated_by_user_id"], updated_at=row["updated_at"],
        )
