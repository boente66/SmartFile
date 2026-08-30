from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"
    NOTIFICATION_REVISION = "welcome-offline-beta5-1"

    def __init__(self, database):
        self.database = database

    def should_notify(self) -> bool:
        row = self.database.fetch_one(
            "SELECT value FROM app_settings WHERE key=?", (self.SETTING_KEY,)
        )
        return row is None or row["value"] != self._marker()

    def acknowledge(self, version: str) -> None:
        if version != __version__:
            return
        self.database.execute_query(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (self.SETTING_KEY, self._marker()),
        )

    @staticmethod
    def message() -> str:
        return (
            "A versão 0.9.0-beta.5 apresenta uma recepção personalizada após o login "
            "e melhora a experiência quando outro SmartFile está offline. Entregas, "
            "solicitações e comprovantes permanecem na fila com retentativa automática, "
            "sem exibir rastreamentos técnicos repetitivos. Os fluxos, permissões, "
            "armazenamento local e sincronização existentes foram preservados."
        )

    @classmethod
    def _marker(cls) -> str:
        return f"{__version__}:{cls.NOTIFICATION_REVISION}"
