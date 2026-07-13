from __future__ import annotations

import os
from datetime import datetime, timezone

from app.cloud.cloud_factory import CloudFactory
from app.cloud.cloud_models import CloudAccount, CloudAuthResult, CloudSettings
from app.cloud.cloud_provider import CloudProvider, Transport
from app.cloud.token_cipher import TokenCipher
from app.database.database import Database


class CloudManager:
    """Gerencia conta/configuração; nunca expõe tokens criptografados à interface."""

    def __init__(self, database: Database, transport: Transport | None = None):
        self.database = database
        self.transport = transport
        self._cipher: TokenCipher | None = None

    @property
    def cipher(self) -> TokenCipher:
        if self._cipher is None:
            self._cipher = TokenCipher(self.database.data_dir / ".cloud_tokens.key")
        return self._cipher

    def settings(self, organization_id: int) -> CloudSettings:
        self.database.execute_query(
            "INSERT OR IGNORE INTO cloud_settings (organization_id, sync_mode, paused) VALUES (?, 'LOCAL', 0)",
            (organization_id,),
        )
        row = self.database.fetch_one("SELECT * FROM cloud_settings WHERE organization_id = ?", (organization_id,))
        return CloudSettings(
            organization_id=row["organization_id"], cloud_account_id=row["cloud_account_id"],
            sync_mode=row["sync_mode"], remote_root_id=row["remote_root_id"],
            last_sync=row["last_sync"], delta_token=row["delta_token"], paused=bool(row["paused"]),
        )

    def account(self, account_id: int) -> CloudAccount:
        row = self.database.fetch_one("SELECT * FROM cloud_accounts WHERE id = ?", (account_id,))
        if row is None:
            raise ValueError("Conta de nuvem não encontrada.")
        return CloudAccount(
            id=row["id"], provider=row["provider"], email=row["email"], display_name=row["display_name"],
            access_token=self.cipher.decrypt(row["access_token"]) or "",
            refresh_token=self.cipher.decrypt(row["refresh_token"]), expires_at=row["expires_at"],
            status=row["status"], created_at=row["created_at"],
        )

    def active_account_for(self, provider: str) -> CloudAccount | None:
        row = self.database.fetch_one(
            """
            SELECT id FROM cloud_accounts WHERE provider = ? AND status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1
            """,
            (provider,),
        )
        return self.account(row["id"]) if row else None

    def begin_authentication(self, provider: str) -> CloudAuthResult:
        return CloudFactory.create(provider, transport=self.transport).authenticate({
            "action": "begin", **self.oauth_credentials(provider),
        })

    def complete_authentication(
        self, organization_id: int, provider: str, code: str, code_verifier: str,
    ) -> CloudAccount:
        result = CloudFactory.create(provider, transport=self.transport).authenticate({
            "action": "complete", "code": code, "code_verifier": code_verifier,
            **self.oauth_credentials(provider),
        })
        account = self._save_account(provider, result)
        self.configure(organization_id, provider, account.id)
        return account

    def configure(self, organization_id: int, sync_mode: str, account_id: int | None = None) -> None:
        if sync_mode == "LOCAL":
            account_id = None
        elif account_id is None:
            raise ValueError("Adicione uma conta antes de ativar a sincronização.")
        self.database.execute_query(
            """
            INSERT INTO cloud_settings (organization_id, cloud_account_id, sync_mode, paused)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(organization_id) DO UPDATE SET
                cloud_account_id = excluded.cloud_account_id,
                sync_mode = excluded.sync_mode,
                paused = 0,
                delta_token = CASE WHEN cloud_settings.sync_mode = excluded.sync_mode THEN cloud_settings.delta_token ELSE NULL END
            """,
            (organization_id, account_id, sync_mode),
        )

    def set_paused(self, organization_id: int, paused: bool) -> None:
        self.database.execute_query(
            "UPDATE cloud_settings SET paused = ? WHERE organization_id = ?",
            (int(paused), organization_id),
        )

    def disconnect(self, organization_id: int) -> None:
        settings = self.settings(organization_id)
        if settings.cloud_account_id:
            self.database.execute_query(
                "UPDATE cloud_accounts SET status = 'DISCONNECTED' WHERE id = ?",
                (settings.cloud_account_id,),
            )
        self.configure(organization_id, "LOCAL")

    def provider_for(self, organization_id: int) -> CloudProvider | None:
        settings = self.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.cloud_account_id is None or settings.paused:
            return None
        account = self.account(settings.cloud_account_id)
        if self._expired(account) and account.refresh_token:
            provider = CloudFactory.create(account.provider, transport=self.transport)
            refreshed = provider.refresh_token(account.refresh_token, self.oauth_credentials(account.provider))
            account = self._update_tokens(account, refreshed)
        return CloudFactory.create(account.provider, account.access_token, self.transport)

    @staticmethod
    def oauth_credentials(provider: str) -> dict[str, str]:
        prefix = "ONEDRIVE" if provider == "ONEDRIVE" else "GOOGLE_DRIVE"
        return {
            "client_id": os.getenv(f"SMARTFILE_{prefix}_CLIENT_ID", ""),
            "client_secret": os.getenv(f"SMARTFILE_{prefix}_CLIENT_SECRET", ""),
            "redirect_uri": os.getenv(f"SMARTFILE_{prefix}_REDIRECT_URI", "http://localhost:8765/callback"),
        }

    def _save_account(self, provider: str, result: CloudAuthResult) -> CloudAccount:
        now = self._now()
        cursor = self.database.execute_query(
            """
            INSERT INTO cloud_accounts (
                provider, email, display_name, access_token, refresh_token, expires_at, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
            """,
            (
                provider, result.email, result.display_name,
                self.cipher.encrypt(result.access_token), self.cipher.encrypt(result.refresh_token),
                result.expires_at.isoformat() if result.expires_at else None, now,
            ),
        )
        return self.account(cursor.lastrowid)

    def _update_tokens(self, account: CloudAccount, result: CloudAuthResult) -> CloudAccount:
        refresh = result.refresh_token or account.refresh_token
        self.database.execute_query(
            """
            UPDATE cloud_accounts SET access_token = ?, refresh_token = ?, expires_at = ?, status = 'ACTIVE'
            WHERE id = ?
            """,
            (
                self.cipher.encrypt(result.access_token), self.cipher.encrypt(refresh),
                result.expires_at.isoformat() if result.expires_at else None, account.id,
            ),
        )
        return self.account(account.id)

    @staticmethod
    def _expired(account: CloudAccount) -> bool:
        if not account.expires_at:
            return False
        try:
            return datetime.fromisoformat(account.expires_at) <= datetime.now(timezone.utc)
        except ValueError:
            return True

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
