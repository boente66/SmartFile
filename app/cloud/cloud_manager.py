from __future__ import annotations

import json
from datetime import datetime, timezone

from app.cloud.cloud_factory import CloudFactory
from app.cloud.cloud_models import CloudAccount, CloudAuthResult, CloudOAuthState, CloudSettings
from app.cloud.cloud_provider import CloudProvider, Transport
from app.cloud.token_cipher import TokenCipher
from app.cloud.token_store import CloudTokenStore
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.database.database import Database
from app.errors.cloud_exceptions import (
    CloudAccountOwnershipError, CloudPermissionError, CloudTokenExpiredError,
)
from app.repositories.cloud_folder_repository import CloudFolderRepository
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
        self.folder_mappings = CloudFolderRepository(database=database)
        self._cleanup_migrated_orphan_tokens()
        self._migrate_legacy_oauth_caches()

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

    def account(self, account_id: int, organization_id: int) -> CloudAccount:
        row = self.database.fetch_one(
            "SELECT * FROM cloud_accounts WHERE id=? AND organization_id=?",
            (account_id, organization_id),
        )
        if row is None:
            if self.database.fetch_one(
                "SELECT 1 FROM cloud_accounts WHERE id=?", (account_id,)
            ) is not None:
                raise CloudAccountOwnershipError(
                    "Esta conta de nuvem pertence a outra organização."
                )
            raise ValueError("Conta de nuvem não encontrada.")
        token_ref = row["token_ref"] if "token_ref" in row.keys() else None
        access_token, refresh_token = self.token_store.load(token_ref)
        if not access_token and row["access_token"] not in {"TOKEN_STORE", ""}:
            # Migração transparente de instalações que guardavam o blob cifrado no SQLite.
            access_token = self.cipher.decrypt(row["access_token"]) or ""
            refresh_token = self.cipher.decrypt(row["refresh_token"])
            token_ref = self.token_store.save(access_token, refresh_token)
            self.database.execute_query(
                """UPDATE cloud_accounts SET token_ref=?,access_token='TOKEN_STORE',
                          refresh_token='TOKEN_STORE'
                   WHERE id=? AND organization_id=?""",
                (token_ref, account_id, organization_id),
            )
        return CloudAccount(
            id=row["id"], organization_id=row["organization_id"],
            provider=row["provider"], email=row["email"], display_name=row["display_name"],
            access_token=access_token, refresh_token=refresh_token, expires_at=row["expires_at"],
            status=row["status"], created_at=row["created_at"],
            token_ref=token_ref,
        )

    def active_account_for(self, provider: str, organization_id: int) -> CloudAccount | None:
        row = self.database.fetch_one(
            """SELECT a.id FROM cloud_accounts a JOIN cloud_settings s
                   ON s.cloud_account_id=a.id AND s.organization_id=a.organization_id
               WHERE a.provider=? AND a.status='ACTIVE'
                 AND a.organization_id=? AND s.organization_id=? LIMIT 1""",
            (provider, organization_id, organization_id),
        )
        return self.account(row["id"], organization_id) if row else None

    def accounts_for_organization(self, organization_id: int) -> list[CloudAccount]:
        """Lista somente identidades pertencentes à organização ativa."""
        self._require("cloud.view")
        rows = self.database.fetch_all(
            """SELECT id FROM cloud_accounts
               WHERE organization_id=? AND status!='DISCONNECTED'
               ORDER BY provider,display_name,email,id""",
            (organization_id,),
        )
        return [self.account(int(row["id"]), organization_id) for row in rows]

    def provider_for_account(
        self, organization_id: int, account_id: int, *, permission: str = "cloud.view",
    ) -> CloudProvider:
        """Resolve uma conta exata; nunca usa a conta ativa de outra organização."""
        self._require(permission)
        account = self.account(account_id, organization_id)
        if self._expired(account):
            if not account.refresh_token:
                raise CloudTokenExpiredError(
                    "A autorização expirou. Conecte novamente sua conta."
                )
            provider = CloudFactory.create(account.provider, transport=self.transport)
            account = self._update_tokens(
                account,
                provider.refresh_token(
                    account.refresh_token, self.oauth_credentials(account.provider)
                ),
            )
        return CloudFactory.create(account.provider, account.access_token, self.transport)

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
        settings = self.settings(organization_id)
        account = None
        if settings.cloud_account_id is not None:
            current = self.account(settings.cloud_account_id, organization_id)
            same_identity = (
                not current.email
                or not result.email
                or current.email.strip().casefold()
                == result.email.strip().casefold()
            )
            if current.provider == provider and same_identity:
                account = self._replace_authentication(current, result)
        if account is None:
            account = self._save_account(organization_id, provider, result)
        self.configure(organization_id, provider, account.id)
        self._audit("CLOUD_CONNECTED", organization_id, account.id, f"Conta {provider} conectada")
        return account

    def configure(self, organization_id: int, sync_mode: str, account_id: int | None = None) -> None:
        self._require("cloud.connect" if sync_mode != "LOCAL" else "cloud.disconnect")
        if sync_mode == "LOCAL":
            account_id = None
        elif account_id is None:
            raise ValueError("Adicione uma conta antes de ativar a sincronização.")
        else:
            account = self.account(account_id, organization_id)
            if account.provider != sync_mode:
                raise ValueError("A conta selecionada pertence a outro provedor de nuvem.")
        current = self.settings(organization_id)
        changed_account = (
            current.sync_mode != sync_mode or current.cloud_account_id != account_id
        )
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO cloud_settings (
                    organization_id,cloud_account_id,sync_mode,paused,remote_root_id,delta_token
                ) VALUES (?,?,?,0,NULL,NULL)
                ON CONFLICT(organization_id) DO UPDATE SET
                    cloud_account_id=excluded.cloud_account_id,
                    sync_mode=excluded.sync_mode,
                    paused=0,
                    remote_root_id=CASE
                        WHEN cloud_settings.sync_mode=excluded.sync_mode
                         AND cloud_settings.cloud_account_id=excluded.cloud_account_id
                        THEN cloud_settings.remote_root_id ELSE NULL END,
                    delta_token=CASE
                        WHEN cloud_settings.sync_mode=excluded.sync_mode
                         AND cloud_settings.cloud_account_id=excluded.cloud_account_id
                        THEN cloud_settings.delta_token ELSE NULL END
                """,
                (organization_id, account_id, sync_mode),
            )
            if changed_account:
                connection.execute(
                    "DELETE FROM cloud_folder_mappings WHERE organization_id=?",
                    (organization_id,),
                )

    def set_paused(self, organization_id: int, paused: bool) -> None:
        self._require("cloud.sync")
        self.database.execute_query(
            "UPDATE cloud_settings SET paused = ? WHERE organization_id = ?",
            (int(paused), organization_id),
        )

    def disconnect(self, organization_id: int) -> None:
        """Compatibilidade: desconectar também remove o login local não compartilhado."""
        self.remove_account(organization_id, audit_action="CLOUD_DISCONNECTED")

    def remove_account(
        self, organization_id: int, *, audit_action: str = "CLOUD_ACCOUNT_REMOVED",
    ) -> None:
        self._require("cloud.disconnect")
        settings = self.settings(organization_id)
        token_ref = None
        provider = None
        if settings.cloud_account_id:
            account = self.account(settings.cloud_account_id, organization_id)
            token_ref = account.token_ref
            provider = account.provider
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO cloud_settings (organization_id,cloud_account_id,sync_mode,paused)
                   VALUES (?,NULL,'LOCAL',0) ON CONFLICT(organization_id) DO UPDATE SET
                   cloud_account_id=NULL,sync_mode='LOCAL',paused=0,delta_token=NULL,remote_root_id=NULL""",
                (organization_id,),
            )
            connection.execute(
                "DELETE FROM cloud_folder_mappings WHERE organization_id=?",
                (organization_id,),
            )
            if settings.cloud_account_id:
                linked = connection.execute(
                    "SELECT COUNT(*) total FROM cloud_settings WHERE cloud_account_id=?",
                    (settings.cloud_account_id,),
                ).fetchone()["total"]
                if linked == 0:
                    connection.execute(
                        "DELETE FROM cloud_accounts WHERE id=? AND organization_id=?",
                        (settings.cloud_account_id, organization_id),
                    )
        if token_ref and self.database.fetch_one(
            "SELECT 1 FROM cloud_accounts WHERE token_ref=? LIMIT 1", (token_ref,)
        ) is None:
            self.token_store.delete(token_ref)
        if provider:
            CloudOAuthConfigService(self.database).delete_cache(
                provider, organization_id
            )
        description = "Conta de nuvem removida" if audit_action == "CLOUD_ACCOUNT_REMOVED" else "Conta de nuvem desconectada"
        self._audit(audit_action, organization_id, settings.cloud_account_id, description)

    def provider_for(self, organization_id: int) -> CloudProvider | None:
        return self._provider_for(organization_id, "cloud.sync", respect_pause=True)

    def quota_provider_for(self, organization_id: int) -> CloudProvider | None:
        """Resolve somente a conta da organização solicitada, com permissão de leitura."""
        return self._provider_for(organization_id, "cloud.view", respect_pause=False)

    def _provider_for(
        self, organization_id: int, permission: str, *, respect_pause: bool,
    ) -> CloudProvider | None:
        self._require(permission)
        settings = self.settings(organization_id)
        if (
            settings.sync_mode == "LOCAL"
            or settings.cloud_account_id is None
            or (respect_pause and settings.paused)
        ):
            return None
        account = self.account(settings.cloud_account_id, organization_id)
        if self._expired(account):
            if account.refresh_token:
                provider = CloudFactory.create(account.provider, transport=self.transport)
                refreshed = provider.refresh_token(account.refresh_token, self.oauth_credentials(account.provider))
            elif account.provider == "ONEDRIVE":
                from app.cloud.cloud_python_auth_service import CloudPythonAuthService
                try:
                    refreshed = CloudPythonAuthService(self.database).authenticate(
                        account.provider, interactive=False,
                        account_hint=account.email,
                        organization_id=organization_id,
                    )
                except Exception as exc:
                    self.database.execute_query(
                        """UPDATE cloud_accounts SET status='REAUTH_REQUIRED'
                           WHERE id=? AND organization_id=?""",
                        (account.id, organization_id),
                    )
                    raise CloudTokenExpiredError(
                        "A autorização expirou. Conecte novamente sua conta."
                    ) from exc
            else:
                self.database.execute_query(
                    """UPDATE cloud_accounts SET status='REAUTH_REQUIRED'
                       WHERE id=? AND organization_id=?""",
                    (account.id, organization_id),
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
        account = self.account(settings.cloud_account_id, organization_id)
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
                """UPDATE cloud_accounts SET status='REAUTH_REQUIRED'
                   WHERE id=? AND organization_id=?""",
                (settings.cloud_account_id, organization_id),
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

    def _save_account(
        self, organization_id: int, provider: str, result: CloudAuthResult,
    ) -> CloudAccount:
        now = self._now()
        token_ref = self.token_store.save(result.access_token, result.refresh_token)
        cursor = self.database.execute_query(
            """
            INSERT INTO cloud_accounts (
                organization_id,provider,email,display_name,access_token,
                refresh_token,expires_at,status,created_at,token_ref
            ) VALUES (?, ?, ?, ?, 'TOKEN_STORE', 'TOKEN_STORE', ?, 'ACTIVE', ?, ?)
            """,
            (
                organization_id, provider, result.email, result.display_name,
                result.expires_at.isoformat() if result.expires_at else None, now, token_ref,
            ),
        )
        return self.account(cursor.lastrowid, organization_id)

    def _update_tokens(self, account: CloudAccount, result: CloudAuthResult) -> CloudAccount:
        refresh = result.refresh_token or account.refresh_token
        token_ref = self.token_store.save(result.access_token, refresh, account.token_ref)
        self.database.execute_query(
            """
            UPDATE cloud_accounts SET access_token='TOKEN_STORE', refresh_token='TOKEN_STORE', token_ref=?, expires_at=?, status='ACTIVE'
            WHERE id=? AND organization_id=?
            """,
            (
                token_ref, result.expires_at.isoformat() if result.expires_at else None,
                account.id, account.organization_id,
            ),
        )
        return self.account(account.id, account.organization_id)

    def _replace_authentication(
        self, account: CloudAccount, result: CloudAuthResult,
    ) -> CloudAccount:
        """Atualiza a conta vinculada sem perder raiz, cursor ou mapeamentos."""

        refresh = result.refresh_token or account.refresh_token
        token_ref = self.token_store.save(
            result.access_token, refresh, account.token_ref
        )
        self.database.execute_query(
            """
            UPDATE cloud_accounts SET
                email=?,display_name=?,access_token='TOKEN_STORE',
                refresh_token='TOKEN_STORE',token_ref=?,expires_at=?,
                status='ACTIVE'
            WHERE id=? AND organization_id=?
            """,
            (
                result.email or account.email,
                result.display_name or account.display_name,
                token_ref,
                (
                    result.expires_at.isoformat()
                    if result.expires_at else None
                ),
                account.id, account.organization_id,
            ),
        )
        return self.account(account.id, account.organization_id)

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

    def _cleanup_migrated_orphan_tokens(self) -> None:
        """Remove segredos sem owner deixados pela migration 21."""

        row = self.database.fetch_one(
            "SELECT value FROM app_settings WHERE key='cloud.v21_orphan_token_refs'"
        )
        if row is None:
            return
        try:
            references = json.loads(row["value"] or "[]")
        except (TypeError, json.JSONDecodeError):
            references = []
        for reference in references:
            if isinstance(reference, str) and reference:
                self.token_store.delete(reference)
        self.database.execute_query(
            "DELETE FROM app_settings WHERE key='cloud.v21_orphan_token_refs'"
        )

    def _migrate_legacy_oauth_caches(self) -> None:
        """Entrega cada cache legado a um único owner e impede uso cross-tenant."""

        config = CloudOAuthConfigService(self.database)
        for provider in ("ONEDRIVE", "GOOGLE_DRIVE"):
            serialized = config.load_cache(provider)
            if not serialized:
                continue
            row = self.database.fetch_one(
                """SELECT organization_id FROM cloud_accounts
                   WHERE provider=? ORDER BY organization_id,id LIMIT 1""",
                (provider,),
            )
            if row is not None:
                config.save_cache(provider, serialized, row["organization_id"])
            config.delete_cache(provider)

    def _audit(self, action: str, organization_id: int, account_id: int | None, description: str) -> None:
        self.audit.record(
            action,
            user_id=getattr(getattr(self.session_context, "current_user", None), "id", None),
            organization_id=organization_id,
            target_type="cloud_account",
            target_id=account_id,
            description=description,
        )
