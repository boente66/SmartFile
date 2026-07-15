from __future__ import annotations

from datetime import datetime, timezone

from app.cloud.cloud_factory import CloudFactory
from app.cloud.cloud_models import CloudAccount, CloudAuthResult, CloudOAuthState, CloudSettings
from app.cloud.cloud_provider import CloudProvider, Transport
from app.cloud.token_cipher import TokenCipher
from app.cloud.token_store import CloudTokenStore
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.database.database import Database
from app.errors.cloud_exceptions import CloudPermissionError, CloudTokenExpiredError
from app.services.audit_service import AuditService


class CloudManager:
    """Gerencia conta/configuração; nunca expõe tokens criptografados à interface."""

    def __init__(self, database: Database, transport: Transport | None = None, session_context=None):
        self.database = database
        self.transport = transport
        self.session_context = session_context
        self._cipher: TokenCipher | None = None
        self.token_store = CloudTokenStore(database.data_dir)
        self.audit = AuditService(database)

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
        token_ref = row["token_ref"] if "token_ref" in row.keys() else None
        access_token, refresh_token = self.token_store.load(token_ref)
        if not access_token and row["access_token"] not in {"TOKEN_STORE", ""}:
            # Migração transparente de instalações que guardavam o blob cifrado no SQLite.
            access_token = self.cipher.decrypt(row["access_token"]) or ""
            refresh_token = self.cipher.decrypt(row["refresh_token"])
            token_ref = self.token_store.save(access_token, refresh_token)
            self.database.execute_query(
                "UPDATE cloud_accounts SET token_ref=?, access_token='TOKEN_STORE', refresh_token='TOKEN_STORE' WHERE id=?",
                (token_ref, account_id),
            )
        return CloudAccount(
            id=row["id"], provider=row["provider"], email=row["email"], display_name=row["display_name"],
            access_token=access_token, refresh_token=refresh_token, expires_at=row["expires_at"],
            status=row["status"], created_at=row["created_at"],
            token_ref=token_ref,
        )

    def active_account_for(self, provider: str, organization_id: int | None = None) -> CloudAccount | None:
        if organization_id is None:
            row = self.database.fetch_one(
                "SELECT id FROM cloud_accounts WHERE provider=? AND status='ACTIVE' ORDER BY id DESC LIMIT 1",
                (provider,),
            )
        else:
            row = self.database.fetch_one(
                """SELECT a.id FROM cloud_accounts a JOIN cloud_settings s ON s.cloud_account_id=a.id
                   WHERE a.provider=? AND a.status='ACTIVE' AND s.organization_id=? LIMIT 1""",
                (provider, organization_id),
            )
        return self.account(row["id"]) if row else None

    def begin_authentication(self, provider: str) -> CloudAuthResult:
        self._require("cloud.connect")
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
        return self.save_authentication_result(organization_id, provider, result)

    def save_authentication_result(
        self, organization_id: int, provider: str, result: CloudAuthResult,
    ) -> CloudAccount:
        """Persiste resultado produzido por MSAL ou google-auth-oauthlib."""
        self._require("cloud.connect")
        if not result.access_token:
            raise ValueError("O provedor não retornou um token de acesso.")
        account = self._save_account(provider, result)
        self.configure(organization_id, provider, account.id)
        self._audit("CLOUD_CONNECTED", organization_id, account.id, f"Conta {provider} conectada")
        return account

    def configure(self, organization_id: int, sync_mode: str, account_id: int | None = None) -> None:
        self._require("cloud.connect" if sync_mode != "LOCAL" else "cloud.disconnect")
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
        self._require("cloud.sync")
        self.database.execute_query(
            "UPDATE cloud_settings SET paused = ? WHERE organization_id = ?",
            (int(paused), organization_id),
        )

    def disconnect(self, organization_id: int) -> None:
        self._require("cloud.disconnect")
        settings = self.settings(organization_id)
        if settings.cloud_account_id:
            account = self.account(settings.cloud_account_id)
            self.database.execute_query(
                "UPDATE cloud_accounts SET status = 'DISCONNECTED' WHERE id = ?",
                (settings.cloud_account_id,),
            )
            self.token_store.delete(account.token_ref)
        self.database.execute_query(
            """INSERT INTO cloud_settings (organization_id,cloud_account_id,sync_mode,paused)
               VALUES (?,NULL,'LOCAL',0) ON CONFLICT(organization_id) DO UPDATE SET
               cloud_account_id=NULL,sync_mode='LOCAL',paused=0,delta_token=NULL""",
            (organization_id,),
        )
        self._audit("CLOUD_DISCONNECTED", organization_id, settings.cloud_account_id, "Conta de nuvem desconectada")

    def provider_for(self, organization_id: int) -> CloudProvider | None:
        self._require("cloud.sync")
        settings = self.settings(organization_id)
        if settings.sync_mode == "LOCAL" or settings.cloud_account_id is None or settings.paused:
            return None
        account = self.account(settings.cloud_account_id)
        if self._expired(account):
            if account.refresh_token:
                provider = CloudFactory.create(account.provider, transport=self.transport)
                refreshed = provider.refresh_token(account.refresh_token, self.oauth_credentials(account.provider))
            elif account.provider == "ONEDRIVE":
                from app.cloud.cloud_python_auth_service import CloudPythonAuthService
                try:
                    refreshed = CloudPythonAuthService(self.database).authenticate(
                        account.provider, interactive=False, account_hint=account.email
                    )
                except Exception as exc:
                    self.database.execute_query(
                        "UPDATE cloud_accounts SET status='REAUTH_REQUIRED' WHERE id=?", (account.id,)
                    )
                    raise CloudTokenExpiredError(
                        "A autorização expirou. Conecte novamente sua conta."
                    ) from exc
            else:
                self.database.execute_query(
                    "UPDATE cloud_accounts SET status='REAUTH_REQUIRED' WHERE id=?", (account.id,)
                )
                raise CloudTokenExpiredError("A autorização expirou. Conecte novamente sua conta.")
            account = self._update_tokens(account, refreshed)
        return CloudFactory.create(account.provider, account.access_token, self.transport)

    def authentication_state(self, organization_id: int, provider: str) -> CloudOAuthState:
        if self.session_context is not None and not self.session_context.has_permission("cloud.view"):
            return CloudOAuthState.DISABLED
        if not CloudOAuthConfigService(self.database).is_provider_configured(provider):
            return CloudOAuthState.NOT_CONFIGURED
        settings = self.settings(organization_id)
        if settings.cloud_account_id is None or settings.sync_mode != provider:
            return CloudOAuthState.DISCONNECTED
        account = self.account(settings.cloud_account_id)
        if account.provider != provider or account.status == "DISCONNECTED":
            return CloudOAuthState.DISCONNECTED
        if account.status == "REAUTH_REQUIRED":
            return CloudOAuthState.REAUTH_REQUIRED
        if account.status == "ERROR":
            return CloudOAuthState.ERROR
        if self._expired(account):
            return CloudOAuthState.TOKEN_EXPIRED
        return CloudOAuthState.CONNECTED

    def mark_reauthentication_required(self, organization_id: int) -> None:
        settings = self.settings(organization_id)
        if settings.cloud_account_id is not None:
            self.database.execute_query(
                "UPDATE cloud_accounts SET status='REAUTH_REQUIRED' WHERE id=?",
                (settings.cloud_account_id,),
            )

    def oauth_credentials(self, provider: str) -> dict[str, str]:
        configured=CloudOAuthConfigService(self.database).provider_config(provider)
        if provider=="ONEDRIVE":
            client_id=configured.get("client_id",""); client_secret=""
        else:
            installed=(configured.get("client_config") or {}).get("installed",{}); client_id=installed.get("client_id",""); client_secret=installed.get("client_secret","")
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": "http://localhost:8765/callback",
        }

    def _save_account(self, provider: str, result: CloudAuthResult) -> CloudAccount:
        now = self._now()
        token_ref = self.token_store.save(result.access_token, result.refresh_token)
        cursor = self.database.execute_query(
            """
            INSERT INTO cloud_accounts (
                provider, email, display_name, access_token, refresh_token, expires_at, status, created_at, token_ref
            ) VALUES (?, ?, ?, 'TOKEN_STORE', 'TOKEN_STORE', ?, 'ACTIVE', ?, ?)
            """,
            (
                provider, result.email, result.display_name,
                result.expires_at.isoformat() if result.expires_at else None, now, token_ref,
            ),
        )
        return self.account(cursor.lastrowid)

    def _update_tokens(self, account: CloudAccount, result: CloudAuthResult) -> CloudAccount:
        refresh = result.refresh_token or account.refresh_token
        token_ref = self.token_store.save(result.access_token, refresh, account.token_ref)
        self.database.execute_query(
            """
            UPDATE cloud_accounts SET access_token='TOKEN_STORE', refresh_token='TOKEN_STORE', token_ref=?, expires_at=?, status='ACTIVE'
            WHERE id = ?
            """,
            (
                token_ref, result.expires_at.isoformat() if result.expires_at else None, account.id,
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

    def _require(self, permission: str) -> None:
        if self.session_context is None:
            return
        try:
            self.session_context.require_permission(permission)
        except Exception as exc:
            raise CloudPermissionError(
                "Você não possui permissão para executar esta operação de nuvem nesta organização."
            ) from exc

    def _audit(self, action: str, organization_id: int, account_id: int | None, description: str) -> None:
        self.audit.record(
            action,
            user_id=getattr(getattr(self.session_context, "current_user", None), "id", None),
            organization_id=organization_id,
            target_type="cloud_account",
            target_id=account_id,
            description=description,
        )
