from __future__ import annotations

import json
import os
from pathlib import Path

from app.cloud.token_cipher import TokenCipher


class CloudOAuthConfigService:
    """Persiste configurações de apps OAuth criptografadas fora do banco documental."""

    def __init__(self, database):
        self.path = database.data_dir / ".cloud_oauth_config"
        self.cipher = TokenCipher(database.data_dir / ".cloud_tokens.key")

    def load(self) -> dict:
        if not self.path.is_file():
            return {}
        encrypted = self.path.read_text(encoding="utf-8")
        raw = self.cipher.decrypt(encrypted)
        return json.loads(raw) if raw else {}

    def save_onedrive(self, client_id: str, tenant: str = "common") -> None:
        client_id = client_id.strip()
        tenant = tenant.strip() or "common"
        if not client_id:
            raise ValueError("Informe o Client ID do aplicativo Microsoft.")
        data = self.load()
        data["ONEDRIVE"] = {"client_id": client_id, "tenant": tenant}
        self._save(data)

    def save_google_client_file(self, source: str) -> None:
        path = Path(source).expanduser().resolve(strict=True)
        if not path.is_file() or path.suffix.lower() != ".json":
            raise ValueError("Selecione o JSON de cliente Desktop do Google.")
        if path.stat().st_size > 1024 * 1024:
            raise ValueError("O arquivo de configuração do Google é muito grande.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("JSON OAuth do Google inválido.") from exc
        installed = payload.get("installed")
        if not isinstance(installed, dict) or not installed.get("client_id"):
            raise ValueError("Use credenciais OAuth do tipo Aplicativo para computador.")
        data = self.load()
        data["GOOGLE_DRIVE"] = {"client_config": {"installed": installed}}
        self._save(data)

    def provider_config(self, provider: str) -> dict:
        return dict(self.load().get(provider) or {})

    def is_configured(self, provider: str) -> bool:
        config = self.provider_config(provider)
        if provider == "ONEDRIVE":
            return bool(config.get("client_id"))
        return bool((config.get("client_config") or {}).get("installed", {}).get("client_id"))

    def load_cache(self, provider: str) -> str | None:
        return (self.load().get("_token_caches") or {}).get(provider)

    def save_cache(self, provider: str, serialized_cache: str) -> None:
        data=self.load(); data.setdefault("_token_caches",{})[provider]=serialized_cache; self._save(data)

    def _save(self, data: dict) -> None:
        encrypted = self.cipher.encrypt(json.dumps(data, ensure_ascii=False)) or ""
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encrypted)
