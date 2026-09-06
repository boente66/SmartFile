from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"
    NOTIFICATION_REVISION = "cloud-admin-beta6-1"

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
            "A versão 0.9.0-beta.6 permite que proprietários e administradores "
            "configurem os provedores OAuth da nuvem em organizações de qualquer "
            "perfil. Editores e visualizadores continuam sem esse acesso, e os "
            "demais privilégios administrativos permanecem preservados."
        )

    @classmethod
    def _marker(cls) -> str:
        return f"{__version__}:{cls.NOTIFICATION_REVISION}"
