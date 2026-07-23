from __future__ import annotations

from app.cloud.cloud_models import CloudFolderMapping
from app.repositories.base_repository import BaseRepository


class CloudFolderRepository(BaseRepository):
    """Mapeia pastas lógicas sem expor detalhes de provider aos Services de domínio."""

    def upsert(self, mapping: CloudFolderMapping) -> CloudFolderMapping:
        self._write(
            """
            INSERT INTO cloud_folder_mappings (
                organization_id,folder_id,provider,remote_id,remote_parent_id,
                remote_name,synced_at
            ) VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(organization_id,folder_id,provider) DO UPDATE SET
                remote_id=excluded.remote_id,
                remote_parent_id=excluded.remote_parent_id,
                remote_name=excluded.remote_name,
                synced_at=excluded.synced_at
            """,
            (
                mapping.organization_id, mapping.folder_id, mapping.provider,
                mapping.remote_id, mapping.remote_parent_id, mapping.remote_name,
                mapping.synced_at,
            ),
        )
        return mapping

    def find(self, organization_id: int, folder_id: int, provider: str) -> CloudFolderMapping | None:
        row = self._fetch_one(
            """SELECT * FROM cloud_folder_mappings
               WHERE organization_id=? AND folder_id=? AND provider=?""",
            (organization_id, folder_id, provider),
        )
        return self._entity(row) if row else None

    def find_all(self, organization_id: int, provider: str) -> list[CloudFolderMapping]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                """SELECT * FROM cloud_folder_mappings
                   WHERE organization_id=? AND provider=? ORDER BY folder_id""",
                (organization_id, provider),
            )
        ]

    def delete(self, organization_id: int, folder_id: int, provider: str) -> bool:
        return self._write(
            """DELETE FROM cloud_folder_mappings
               WHERE organization_id=? AND folder_id=? AND provider=?""",
            (organization_id, folder_id, provider),
        ).rowcount > 0

    def delete_for_organization(self, organization_id: int) -> int:
        return self._write(
            "DELETE FROM cloud_folder_mappings WHERE organization_id=?",
            (organization_id,),
        ).rowcount

    @staticmethod
    def _entity(row) -> CloudFolderMapping:
        return CloudFolderMapping(
            organization_id=row["organization_id"],
            folder_id=row["folder_id"],
            provider=row["provider"],
            remote_id=row["remote_id"],
            remote_parent_id=row["remote_parent_id"],
            remote_name=row["remote_name"],
            synced_at=row["synced_at"],
        )
