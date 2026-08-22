from __future__ import annotations

from app.cloud.cloud_models import CloudStorageQuota


class CloudStorageQuotaService:
    """Consulta a capacidade remota sem misturá-la à quota lógica do GED."""

    def __init__(self, manager):
        self.manager = manager
        self._snapshots: dict[tuple[int, int, str], CloudStorageQuota] = {}

    def fetch(self, organization_id: int) -> CloudStorageQuota | None:
        settings = self.manager.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.cloud_account_id is None:
            return None
        provider = self.manager.quota_provider_for(organization_id)
        if provider is None:
            return None
        quota = provider.get_storage_quota()
        self._snapshots[self._key(organization_id)] = quota
        return quota

    def last_known(self, organization_id: int) -> CloudStorageQuota | None:
        settings = self.manager.settings(organization_id)
        if settings.cloud_account_id is None:
            return None
        return self._snapshots.get(self._key(organization_id))

    def clear(self, organization_id: int) -> None:
        for key in tuple(self._snapshots):
            if key[0] == organization_id:
                self._snapshots.pop(key, None)

    def _key(self, organization_id: int) -> tuple[int, int, str]:
        settings = self.manager.settings(organization_id)
        return (
            organization_id,
            int(settings.cloud_account_id or 0),
            settings.sync_mode,
        )
