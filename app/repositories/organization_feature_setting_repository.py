from __future__ import annotations

from app.entities.organization_feature_setting_entity import OrganizationFeatureSettingEntity
from app.repositories.base_repository import BaseRepository


class OrganizationFeatureSettingRepository(BaseRepository):
    def find_by_organization(
        self, organization_id: int,
    ) -> list[OrganizationFeatureSettingEntity]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                """
                SELECT * FROM organization_feature_settings
                WHERE organization_id=? ORDER BY feature_code
                """,
                (organization_id,),
            )
        ]

    def save(
        self, entity: OrganizationFeatureSettingEntity,
    ) -> OrganizationFeatureSettingEntity:
        self._write(
            """
            INSERT INTO organization_feature_settings (
                organization_id, feature_code, enabled,
                updated_by_user_id, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(organization_id, feature_code) DO UPDATE SET
                enabled=excluded.enabled,
                updated_by_user_id=excluded.updated_by_user_id,
                updated_at=excluded.updated_at
            """,
            (
                entity.organization_id,
                entity.feature_code,
                int(entity.enabled),
                entity.updated_by_user_id,
                entity.updated_at,
            ),
        )
        return entity

    def save_all(
        self, entities: list[OrganizationFeatureSettingEntity],
    ) -> None:
        for entity in entities:
            self.save(entity)

    @staticmethod
    def _entity(row) -> OrganizationFeatureSettingEntity:
        return OrganizationFeatureSettingEntity(
            organization_id=row["organization_id"],
            feature_code=row["feature_code"],
            enabled=bool(row["enabled"]),
            updated_by_user_id=row["updated_by_user_id"],
            updated_at=row["updated_at"],
        )
