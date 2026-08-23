from __future__ import annotations

from app.version import __version__


class VersionNotificationService:
    """Controla a notificação local exibida uma vez após cada atualização."""

    SETTING_KEY = "last_notified_version"
    NOTIFICATION_REVISION = "documents-workspace-beta3-1"

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
            "O módulo Documentos ganhou uma organização visual mais compacta, com cabeçalho "
            "de organização, nuvem e armazenamento, barra de ações, filtros recolhíveis, "
            "breadcrumb das pastas e controles para mostrar ou ocultar navegação e detalhes. "
            "Os fluxos, permissões, armazenamento local e sincronização existentes foram "
            "preservados."
        )

    @classmethod
    def _marker(cls) -> str:
        return f"{__version__}:{cls.NOTIFICATION_REVISION}"
