from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from app.cloud.cloud_models import CloudAuthResult
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.cloud.cloud_provider import CloudAuthenticationError
from app.errors.cloud_exceptions import (
    CloudAuthorizationCancelledError,
    CloudAuthorizationDeniedError,
    CloudConfigurationMissingError,
    CloudTokenExpiredError,
)


class CloudPythonAuthService:
    """OAuth interativo por bibliotecas Python próprias para aplicativos desktop."""

    GOOGLE_SCOPES = [
        "openid", "email", "profile",
        "https://www.googleapis.com/auth/drive.file",
    ]
    MICROSOFT_SCOPES = ["User.Read", "Files.ReadWrite"]

    def __init__(self, database):
        self.config = CloudOAuthConfigService(database)

    def authenticate(self, provider: str, *, interactive: bool = True) -> CloudAuthResult:
        if provider == "ONEDRIVE":
            return self._authenticate_onedrive(interactive=interactive)
        if provider == "GOOGLE_DRIVE":
            return self._authenticate_google()
        raise CloudAuthenticationError("Provedor de nuvem inválido.")

    def _authenticate_onedrive(self, *, interactive: bool = True) -> CloudAuthResult:
        try:
            import msal
        except ImportError as exc:
            raise CloudAuthenticationError("Instale a dependência Python 'msal'.") from exc
        config = self.config.provider_config("ONEDRIVE")
        if not config.get("client_id"):
            raise CloudConfigurationMissingError(
                "A integração com o OneDrive ainda não foi configurada pelo administrador do SmartFile."
            )
        authority = f"https://login.microsoftonline.com/{config.get('tenant') or 'common'}"
        cache=msal.SerializableTokenCache(); serialized=self.config.load_cache("ONEDRIVE")
        if serialized: cache.deserialize(serialized)
        application = msal.PublicClientApplication(config["client_id"], authority=authority, token_cache=cache)
        accounts=application.get_accounts(); result=application.acquire_token_silent(self.MICROSOFT_SCOPES,account=accounts[0]) if accounts else None
        if not result and interactive:
            result = application.acquire_token_interactive(scopes=self.MICROSOFT_SCOPES,redirect_uri="http://localhost",prompt="select_account")
        if not result:
            raise CloudTokenExpiredError(
                "A autorização expirou. Conecte novamente sua conta."
            )
        if cache.has_state_changed:self.config.save_cache("ONEDRIVE",cache.serialize())
        if "access_token" not in result:
            error = str(result.get("error") or "")
            if error in {"access_denied", "consent_required"}:
                raise CloudAuthorizationDeniedError(
                    "A autorização não foi concedida. O SmartFile não poderá sincronizar esta organização."
                )
            raise CloudAuthorizationCancelledError(
                "A conexão foi cancelada. Nenhuma conta foi vinculada."
            )
        claims = result.get("id_token_claims") or {}
        return CloudAuthResult(
            access_token=result["access_token"],
            refresh_token=result.get("refresh_token"),
            expires_at=datetime.now(timezone.utc)+timedelta(seconds=int(result.get("expires_in",3600))),
            email=claims.get("preferred_username") or claims.get("email"),
            display_name=claims.get("name"),
        )

    def _authenticate_google(self) -> CloudAuthResult:
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
        except ImportError as exc:
            raise CloudAuthenticationError("Instale a dependência Python 'google-auth-oauthlib'.") from exc
        config = self.config.provider_config("GOOGLE_DRIVE")
        client_config = config.get("client_config")
        if not client_config:
            raise CloudConfigurationMissingError(
                "A integração com o Google Drive ainda não foi configurada pelo administrador do SmartFile."
            )
        flow = InstalledAppFlow.from_client_config(client_config, self.GOOGLE_SCOPES)
        try:
            credentials = flow.run_local_server(
                host="localhost", port=0, open_browser=True,
                authorization_prompt_message="Abrindo autenticação do Google Drive...",
                success_message="Autenticação concluída. Você pode fechar esta janela e voltar ao SmartFile.",
                timeout_seconds=180,
            )
        except (KeyboardInterrupt, SystemExit) as exc:
            raise CloudAuthorizationCancelledError(
                "A conexão foi cancelada. Nenhuma conta foi vinculada."
            ) from exc
        profile = self._google_profile(credentials.token)
        expiry = credentials.expiry
        if expiry and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return CloudAuthResult(
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            expires_at=expiry,
            email=profile.get("email"), display_name=profile.get("name"),
        )

    @staticmethod
    def _google_profile(access_token: str) -> dict:
        request = Request(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode())
        except Exception:
            return {}
