from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class TokenCipher:
    """Abstração substituível para criptografia de tokens em repouso."""

    def __init__(self, key_path: Path):
        self.key_path = key_path
        self._fernet = Fernet(self._load_or_create_key())

    def encrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str | None) -> str | None:
        if not value:
            return None
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("Não foi possível descriptografar as credenciais da nuvem.") from exc

    def _load_or_create_key(self) -> bytes:
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        if self.key_path.is_file():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        descriptor = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(key)
        return key
