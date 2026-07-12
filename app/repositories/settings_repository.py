from __future__ import annotations

from app.entities.settings_entity import SettingsEntity
from app.repositories.base_repository import BaseRepository


class SettingsRepository(BaseRepository):
    def set(self, entity: SettingsEntity) -> SettingsEntity:
        self._write(
            """
            INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (entity.key, entity.value, entity.updated_at),
        )
        return entity

    def find_by_key(self, key: str) -> SettingsEntity | None:
        row = self._fetch_one("SELECT * FROM settings WHERE key = ?", (key,))
        return SettingsEntity(**dict(row)) if row else None

    def find_all(self) -> list[SettingsEntity]:
        return [SettingsEntity(**dict(row)) for row in self._fetch_all("SELECT * FROM settings ORDER BY key")]

    def delete(self, key: str) -> bool:
        return self._write("DELETE FROM settings WHERE key = ?", (key,)).rowcount > 0
