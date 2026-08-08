from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"

    def __init__(self, database):
        self.database = database

    def should_notify(self) -> bool:
        row = self.database.fetch_one(
            "SELECT value FROM app_settings WHERE key=?", (self.SETTING_KEY,)
        )
        return row is None or row["value"] != __version__

    def acknowledge(self, version: str) -> None:
        if version != __version__:
            return
        self.database.execute_query(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (self.SETTING_KEY, version),
        )

    @staticmethod
    def message() -> str:
        return (
            "A camada empresarial foi consolidada: recursos opcionais por organização, "
            "transporte corporativo independente da nuvem e responsáveis validados em "
            "solicitações documentais."
        )
