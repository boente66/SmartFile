from __future__ import annotations

import secrets
import hashlib
from datetime import datetime, timedelta, timezone

from app.auth.password_service import PasswordService
from app.entities.password_recovery_code_entity import PasswordRecoveryCodeEntity
from app.repositories.password_recovery_code_repository import (
    PasswordRecoveryCodeRepository,
)


class PasswordRecoveryService:
    """Gera e valida códigos offline de uso único."""

    ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    CODE_COUNT = 5
    VALIDITY_DAYS = 365

    def __init__(self, database):
        self.repository = PasswordRecoveryCodeRepository(database=database)
        self.passwords = PasswordService()

    def has_active_codes(self, user_id: int) -> bool:
        return self.repository.count_active(user_id, self._now()) > 0

    def generate_codes(
        self, user_id: int, count: int = CODE_COUNT
    ) -> tuple[str, ...]:
        if count < 1 or count > 20:
            raise ValueError("Quantidade de códigos de recuperação inválida.")
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + timedelta(days=self.VALIDITY_DAYS)).isoformat()
        self.repository.invalidate_active(user_id, created_at)
        plain_codes: list[str] = []
        for _ in range(count):
            code = self._new_code()
            self.repository.create(
                PasswordRecoveryCodeEntity(
                    user_id=user_id,
                    code_lookup=self._lookup(code),
                    code_hash=self.passwords.hash_password(self._canonical(code)),
                    created_at=created_at,
                    expires_at=expires_at,
                )
            )
            plain_codes.append(code)
        return tuple(plain_codes)

    def verify_and_consume(self, user_id: int, candidate: str) -> bool:
        canonical = self._canonical(candidate)
        if len(canonical) != 18 or not canonical.startswith("SF"):
            return False
        now = self._now()
        entity = self.repository.find_active_by_lookup(
            user_id, self._lookup(canonical), now
        )
        return bool(
            entity
            and self.passwords.verify_password(canonical, entity.code_hash)
            and self.repository.mark_used(entity.id, now)
        )

    def invalidate_codes(self, user_id: int) -> int:
        return self.repository.invalidate_active(user_id, self._now())

    @classmethod
    def _new_code(cls) -> str:
        body = "".join(secrets.choice(cls.ALPHABET) for _ in range(16))
        return "SF-" + "-".join(body[index:index + 4] for index in range(0, 16, 4))

    @staticmethod
    def _canonical(code: str) -> str:
        return "".join(character for character in code.upper() if character.isalnum())

    @classmethod
    def _lookup(cls, code: str) -> str:
        return hashlib.sha256(cls._canonical(code).encode("ascii")).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
