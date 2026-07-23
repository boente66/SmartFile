from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.cloud.cloud_models import CloudConfigurationSource
from app.cloud.token_cipher import TokenCipher
from app.cloud.token_store import CloudTokenStore
from app.errors.cloud_exceptions import (
    CloudConfigurationInvalidError,
    CloudConfigurationMissingError,
)
from app.system.resources import resource_path


class CloudOAuthConfigurationService:
    """Resolve configuração pública do aplicativo sem misturá-la aos tokens do usuário."""

    PROVIDERS = {"ONEDRIVE", "GOOGLE_DRIVE"}

    def __init__(self, database, bundled_dir: Path | None = None):
        config_dir = database.paths.config
        self.path = config_dir / ".cloud_oauth_config"
        self.key_path = config_dir / ".cloud_tokens.key"
        self._cipher: TokenCipher | None = None
        self.token_store = CloudTokenStore(config_dir)
        self.bundled_dir = bundled_dir or resource_path("app/cloud/resources")

    @property
    def cipher(self) -> TokenCipher:
        if self._cipher is None:
            self._cipher = TokenCipher(self.key_path)
        return self._cipher

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {}
        try:
            raw = self.cipher.decrypt(self.path.read_text(encoding="utf-8"))
            return json.loads(raw) if raw else {}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise CloudConfigurationInvalidError(
                "A configuração administrativa da nuvem está inválida."
            ) from exc

    def get_provider_config(self, provider: str) -> dict[str, Any]:
        provider = self._provider(provider)
        for _source, config in self._candidates(provider):
            if self.validate_configuration(provider, config, raise_error=False):
                return config
        return {}

    def get_onedrive_config(self) -> dict[str, Any]:
        return self.get_provider_config("ONEDRIVE")

    def get_google_config(self) -> dict[str, Any]:
        return self.get_provider_config("GOOGLE_DRIVE")

    def provider_config(self, provider: str) -> dict[str, Any]:
        """Compatibilidade com a API pública anterior."""
        return self.get_provider_config(provider)

    def config_source(self, provider: str) -> CloudConfigurationSource:
        provider = self._provider(provider)
        for source, config in self._candidates(provider):
            if self.validate_configuration(provider, config, raise_error=False):
                return source
        return CloudConfigurationSource.MISSING

    def is_provider_configured(self, provider: str) -> bool:
        return self.config_source(provider) != CloudConfigurationSource.MISSING

    def is_configured(self, provider: str) -> bool:
        return self.is_provider_configured(provider)

    def validate_configuration(
        self, provider: str, config: dict[str, Any] | None = None, *, raise_error: bool = True,
    ) -> bool:
        provider = self._provider(provider)
        config = config if config is not None else self.get_provider_config(provider)
        if provider == "ONEDRIVE":
            valid = bool(str(config.get("client_id", "")).strip())
        else:
            installed = (config.get("client_config") or {}).get("installed") or {}
            valid = bool(
                installed.get("client_id")
                and installed.get("auth_uri")
                and installed.get("token_uri")
                and installed.get("redirect_uris")
            )
        if not valid and raise_error:
            raise CloudConfigurationMissingError(
                f"A integração com o {self.display_name(provider)} ainda não foi configurada "
                "pelo administrador do SmartFile."
            )
        return valid

    def save_onedrive(self, client_id: str, tenant: str = "common") -> None:
        config = {"client_id": client_id.strip(), "tenant": tenant.strip() or "common"}
        if not self.validate_configuration("ONEDRIVE", config, raise_error=False):
            raise CloudConfigurationInvalidError("Informe o Client ID do aplicativo Microsoft.")
        data = self.load()
        data["ONEDRIVE"] = config
        self._save(data)

    def save_google_client_file(self, source: str) -> None:
        try:
            path = Path(source).expanduser().resolve(strict=True)
            if not path.is_file() or path.suffix.lower() != ".json" or path.stat().st_size > 1024 * 1024:
                raise CloudConfigurationInvalidError("Selecione o JSON de cliente Desktop do Google.")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CloudConfigurationInvalidError("JSON OAuth do Google inválido.") from exc
        config = {"client_config": {"installed": payload.get("installed")}}
        if not self.validate_configuration("GOOGLE_DRIVE", config, raise_error=False):
            raise CloudConfigurationInvalidError(
                "Use credenciais OAuth do tipo Aplicativo para computador."
            )
        data = self.load()
        data["GOOGLE_DRIVE"] = config
        self._save(data)

    def load_cache(self, provider: str) -> str | None:
        provider = self._provider(provider)
        data = self.load()
        reference = (data.get("_token_cache_refs") or {}).get(provider)
        if reference:
            return self.token_store.load_payload(reference)
        legacy = (data.get("_token_caches") or {}).get(provider)
        if legacy:
            self.save_cache(provider, legacy)
        return legacy

    def save_cache(self, provider: str, serialized_cache: str) -> None:
        provider = self._provider(provider)
        data = self.load()
        references = data.setdefault("_token_cache_refs", {})
        reference = references.get(provider) or f"oauth-cache:{provider.lower()}"
        references[provider] = self.token_store.save_payload(serialized_cache, reference)
        caches = data.get("_token_caches") or {}
        caches.pop(provider, None)
        if caches:
            data["_token_caches"] = caches
        else:
            data.pop("_token_caches", None)
        self._save(data)

    def delete_cache(self, provider: str) -> None:
        """Remove somente o cache OAuth do provedor, preservando a configuração pública."""
        provider = self._provider(provider)
        data = self.load()
        references = data.get("_token_cache_refs") or {}
        reference = references.pop(provider, None)
        if reference:
            self.token_store.delete(reference)
        if references:
            data["_token_cache_refs"] = references
        else:
            data.pop("_token_cache_refs", None)
        caches = data.get("_token_caches") or {}
        caches.pop(provider, None)
        if caches:
            data["_token_caches"] = caches
        else:
            data.pop("_token_caches", None)
        self._save(data)

    def _candidates(self, provider: str):
        bundled = self._bundled(provider)
        if bundled:
            yield CloudConfigurationSource.BUNDLED, bundled
        environment = self._environment(provider, development=False)
        if environment:
            yield CloudConfigurationSource.ENVIRONMENT, environment
        admin = self.load().get(provider) or {}
        if admin:
            yield CloudConfigurationSource.ADMIN_LOCAL, dict(admin)
        development = self._environment(provider, development=True)
        if development:
            yield CloudConfigurationSource.DEVELOPMENT, development

    def _bundled(self, provider: str) -> dict[str, Any]:
        filename = "onedrive.json" if provider == "ONEDRIVE" else "google_drive.json"
        path = self.bundled_dir / filename
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if provider == "GOOGLE_DRIVE" and "client_config" not in payload:
                payload = {"client_config": payload}
            return payload
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _environment(provider: str, *, development: bool) -> dict[str, Any]:
        prefix = "SMARTFILE_DEV_" if development else "SMARTFILE_"
        if provider == "ONEDRIVE":
            client_id = os.getenv(f"{prefix}ONEDRIVE_CLIENT_ID", "").strip()
            return {"client_id": client_id, "tenant": os.getenv(f"{prefix}ONEDRIVE_TENANT", "common")} if client_id else {}
        raw = os.getenv(f"{prefix}GOOGLE_DRIVE_CLIENT_CONFIG", "").strip()
        path = os.getenv(f"{prefix}GOOGLE_DRIVE_CLIENT_CONFIG_FILE", "").strip()
        try:
            payload = json.loads(raw) if raw else json.loads(Path(path).expanduser().read_text(encoding="utf-8")) if path else None
        except (OSError, json.JSONDecodeError):
            return {}
        if payload:
            return {"client_config": payload if "installed" in payload else {"installed": payload}}
        client_id = os.getenv(f"{prefix}GOOGLE_DRIVE_CLIENT_ID", "").strip()
        if not client_id:
            return {}
        installed = {
            "client_id": client_id,
            "client_secret": os.getenv(f"{prefix}GOOGLE_DRIVE_CLIENT_SECRET", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
        return {"client_config": {"installed": installed}}

    def _save(self, data: dict[str, Any]) -> None:
        encrypted = self.cipher.encrypt(json.dumps(data, ensure_ascii=False)) or ""
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encrypted)

    @classmethod
    def _provider(cls, provider: str) -> str:
        normalized = str(provider).upper()
        if normalized not in cls.PROVIDERS:
            raise CloudConfigurationInvalidError("Provedor de nuvem inválido.")
        return normalized

    @staticmethod
    def display_name(provider: str) -> str:
        return "OneDrive" if provider == "ONEDRIVE" else "Google Drive"


# Nome anterior preservado para não quebrar imports públicos.
CloudOAuthConfigService = CloudOAuthConfigurationService
