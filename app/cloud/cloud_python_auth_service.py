from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

from app.cloud.cloud_models import CloudAuthResult
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.cloud.cloud_provider import CloudAuthenticationError
from app.errors.cloud_exceptions import (
    CloudAuthorizationCancelledError,
    CloudAuthorizationDeniedError,
    CloudAuthorizationTimeoutError,
    CloudConfigurationMissingError,
    CloudTokenExpiredError,
)

logger = logging.getLogger(__name__)


class CloudPythonAuthService:
    """OAuth interativo por bibliotecas Python próprias para aplicativos desktop."""

    GOOGLE_SCOPES = [
        "openid", "email", "profile",
        "https://www.googleapis.com/auth/drive.file",
    ]
    MICROSOFT_SCOPES = ["User.Read", "Files.ReadWrite"]

    def __init__(self, database):
        self.config = CloudOAuthConfigService(database)

    def authenticate(
        self, provider: str, *, interactive: bool = True, account_hint: str | None = None,
    ) -> CloudAuthResult:
        if provider == "ONEDRIVE":
            return self._authenticate_onedrive(
                interactive=interactive, account_hint=account_hint
            )
        if provider == "GOOGLE_DRIVE":
            return self._authenticate_google()
        raise CloudAuthenticationError("Provedor de nuvem inválido.")

    def _authenticate_onedrive(
        self, *, interactive: bool = True, account_hint: str | None = None,
    ) -> CloudAuthResult:
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
        accounts = application.get_accounts(username=account_hint) if account_hint else application.get_accounts()
        result = application.acquire_token_silent(
            self.MICROSOFT_SCOPES, account=accounts[0]
        ) if accounts else None
        if not result and interactive:
            try:
                result = application.acquire_token_interactive(
                    scopes=self.MICROSOFT_SCOPES,
                    prompt="select_account",
                    login_hint=account_hint,
                    timeout=180,
                )
            except TimeoutError as exc:
                raise CloudAuthorizationTimeoutError(
                    "A autenticação não foi concluída dentro do tempo esperado."
                ) from exc
            except OSError as exc:
                raise CloudAuthenticationError(
                    "Não foi possível iniciar o callback local da Microsoft."
                ) from exc
            except Exception as exc:
                logger.warning(
                    "Falha no fluxo interativo MSAL: %s", type(exc).__name__
                )
                raise CloudAuthenticationError(
                    self._microsoft_exception_message(exc)
                ) from exc
        if not result:
            if interactive:
                raise CloudAuthorizationCancelledError(
                    "A conexão foi cancelada. Nenhuma conta foi vinculada."
                )
            raise CloudTokenExpiredError("A autorização expirou. Conecte novamente sua conta.")
        if cache.has_state_changed:self.config.save_cache("ONEDRIVE",cache.serialize())
        if "access_token" not in result:
            error = str(result.get("error") or "")
            if error in {"access_denied", "consent_required"}:
                raise CloudAuthorizationDeniedError(
                    "A autorização não foi concedida. O SmartFile não poderá sincronizar esta organização."
                )
            raise CloudAuthenticationError(self._microsoft_result_message(result))
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
        except TimeoutError as exc:
            raise CloudAuthorizationTimeoutError(
                "A autenticação não foi concluída dentro do tempo esperado."
            ) from exc
        except OSError as exc:
            raise CloudAuthenticationError(
                "Não foi possível iniciar o callback local do Google Drive."
            ) from exc
        except Exception as exc:
            message = str(exc).lower()
            if "access_denied" in message or "consent" in message:
                raise CloudAuthorizationDeniedError(
                    "A autorização não foi concedida. O SmartFile não poderá sincronizar esta organização."
                ) from exc
            raise CloudAuthenticationError(
                "Não foi possível concluir a autorização da conta Google."
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

    @staticmethod
    def _microsoft_result_message(result: dict) -> str:
        description = str(result.get("error_description") or "")
        code_match = re.search(r"AADSTS\d+", description)
        code = code_match.group(0) if code_match else ""
        messages = {
            "AADSTS50011": "O redirect URI do SmartFile não está cadastrado no Microsoft Entra. Configure http://localhost como aplicativo Mobile e desktop.",
            "AADSTS700016": "O Client ID não foi encontrado no tenant configurado. Confira o Client ID e o tenant no SmartFile.",
            "AADSTS7000218": "O aplicativo Microsoft não está habilitado como cliente público. Ative 'Permitir fluxos de cliente público' no Microsoft Entra.",
            "AADSTS65001": "O consentimento para acessar o OneDrive ainda não foi concedido.",
        }
        if code in messages:
            return f"{messages[code]} ({code})"
        error = str(result.get("error") or "")
        if error == "access_denied":
            return "A autorização foi recusada. Nenhuma conta foi vinculada."
        if error:
            return f"A Microsoft não concluiu a autorização ({error}). Verifique a configuração do aplicativo."
        return "A conexão foi cancelada. Nenhuma conta foi vinculada."

    @staticmethod
    def _microsoft_exception_message(exc: Exception) -> str:
        message = str(exc)
        if "redirect_uri" in message and "multiple values" in message:
            return "A biblioteca de autenticação Microsoft está incompatível com a configuração do callback local."
        if "browser" in message.lower():
            return "Não foi possível abrir o navegador para autenticar a conta Microsoft."
        return "Não foi possível concluir a autorização da conta Microsoft. Confira o redirect URI e o cliente público no Microsoft Entra."
