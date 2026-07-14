from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from app.cloud.token_cipher import TokenCipher
from app.errors.cloud_exceptions import CloudTokenStoreError


class CloudTokenStore:
    """Armazena tokens fora do SQLite, preferindo o cofre do sistema operacional."""

    SERVICE_NAME = "SmartFile.Cloud"

    def __init__(self, data_dir: Path):
        self.path = data_dir / ".cloud_token_store"
        self.key_path = data_dir / ".cloud_tokens.key"
        self._cipher: TokenCipher | None = None

    @property
    def cipher(self) -> TokenCipher:
        if self._cipher is None:
            self._cipher = TokenCipher(self.key_path)
        return self._cipher

    def save(self, access_token: str, refresh_token: str | None, reference: str | None = None) -> str:
        if not access_token:
            raise CloudTokenStoreError("O provedor não retornou credenciais válidas.")
        payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
        return self.save_payload(payload, reference)

    def save_payload(self, payload: str, reference: str | None = None) -> str:
        reference = reference or f"cloud:{uuid4()}"
        if not self._keyring_set(reference, payload):
            records = self._load_fallback()
            records[reference] = payload
            self._save_fallback(records)
        return reference

    def load(self, reference: str | None) -> tuple[str, str | None]:
        if not reference:
            return "", None
        payload = self.load_payload(reference)
        if not payload:
            return "", None
        try:
            data = json.loads(payload)
            return str(data.get("access_token") or ""), data.get("refresh_token")
        except json.JSONDecodeError as exc:
            raise CloudTokenStoreError("As credenciais salvas da nuvem estão inválidas.") from exc

    def load_payload(self, reference: str | None) -> str | None:
        if not reference:
            return None
        return self._keyring_get(reference) or self._load_fallback().get(reference)

    def delete(self, reference: str | None) -> None:
        if not reference:
            return
        self._keyring_delete(reference)
        records = self._load_fallback()
        if reference in records:
            del records[reference]
            self._save_fallback(records)

    def _load_fallback(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        try:
            raw = self.cipher.decrypt(self.path.read_text(encoding="utf-8"))
            return json.loads(raw) if raw else {}
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise CloudTokenStoreError("Não foi possível abrir o cofre local da nuvem.") from exc

    def _save_fallback(self, records: dict[str, str]) -> None:
        encrypted = self.cipher.encrypt(json.dumps(records)) or ""
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encrypted)

    @classmethod
    def _keyring_get(cls, reference: str) -> str | None:
        try:
            import keyring
            return keyring.get_password(cls.SERVICE_NAME, reference)
        except Exception:
            return None

    @classmethod
    def _keyring_set(cls, reference: str, payload: str) -> bool:
        try:
            import keyring
            keyring.set_password(cls.SERVICE_NAME, reference, payload)
            return True
        except Exception:
            return False

    @classmethod
    def _keyring_delete(cls, reference: str) -> None:
        try:
            import keyring
            keyring.delete_password(cls.SERVICE_NAME, reference)
        except Exception:
            pass
