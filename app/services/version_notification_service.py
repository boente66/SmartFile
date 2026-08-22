from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"
    NOTIFICATION_REVISION = "cloud-quota-platform-update-1"

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
            "O cabeçalho de Documentos agora separa o armazenamento local do SmartFile da "
            "capacidade real do OneDrive ou Google Drive. A consulta ocorre em segundo plano "
            "e não interfere na sincronização. O SmartFile também pode avisar quando houver "
            "uma nova versão compatível com Linux ou Windows e abrir o instalador oficial "
            "no navegador, sempre mediante confirmação do usuário. A descoberta automática "
            "de instalações LAN e a configuração manual continuam disponíveis."
        )

    @classmethod
    def _marker(cls) -> str:
        return f"{__version__}:{cls.NOTIFICATION_REVISION}"
