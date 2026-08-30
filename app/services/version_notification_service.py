from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"
    NOTIFICATION_REVISION = "multicloud-workspace-beta4-1"

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
            "A versão 0.9.0-beta.4 adiciona o Acervo Remoto Multicloud aos perfis "
            "Pessoal e Estudante. Pastas existentes do OneDrive e Google Drive podem "
            "ser montadas como espelhos lógicos sem copiar arquivos. Solicitações, "
            "prazos e entregas permanecem exclusivos do perfil Empresarial. Contas "
            "Google já conectadas precisam de novo consentimento para ler acervos existentes. "
            "Os fluxos, permissões, armazenamento local e sincronização existentes "
            "foram preservados."
        )

    @classmethod
    def _marker(cls) -> str:
        return f"{__version__}:{cls.NOTIFICATION_REVISION}"
