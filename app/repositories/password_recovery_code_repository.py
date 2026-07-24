from app.entities.password_recovery_code_entity import PasswordRecoveryCodeEntity
from app.repositories.base_repository import BaseRepository


class PasswordRecoveryCodeRepository(BaseRepository):
    def create(
        self, entity: PasswordRecoveryCodeEntity
    ) -> PasswordRecoveryCodeEntity:
        cursor = self._write(
            """INSERT INTO password_recovery_codes
               (user_id,code_lookup,code_hash,created_at,expires_at,used_at)
               VALUES (?,?,?,?,?,?)""",
            (
                entity.user_id,
                entity.code_lookup,
                entity.code_hash,
                entity.created_at,
                entity.expires_at,
                entity.used_at,
            ),
        )
        entity.id = cursor.lastrowid
        return entity

    def find_active_by_user(
        self, user_id: int, now: str
    ) -> list[PasswordRecoveryCodeEntity]:
        rows = self._fetch_all(
            """SELECT * FROM password_recovery_codes
               WHERE user_id=? AND used_at IS NULL AND expires_at>?
               ORDER BY id""",
            (user_id, now),
        )
        return [self._entity(row) for row in rows]

    def find_active_by_lookup(
        self, user_id: int, code_lookup: str, now: str
    ) -> PasswordRecoveryCodeEntity | None:
        row = self._fetch_one(
            """SELECT * FROM password_recovery_codes
               WHERE user_id=? AND code_lookup=? AND used_at IS NULL
                 AND expires_at>?""",
            (user_id, code_lookup, now),
        )
        return self._entity(row) if row else None

    def count_active(self, user_id: int, now: str) -> int:
        row = self._fetch_one(
            """SELECT COUNT(*) total FROM password_recovery_codes
               WHERE user_id=? AND used_at IS NULL AND expires_at>?""",
            (user_id, now),
        )
        return int(row["total"])

    def mark_used(self, code_id: int, used_at: str) -> bool:
        return (
            self._write(
                """UPDATE password_recovery_codes SET used_at=?
                   WHERE id=? AND used_at IS NULL""",
                (used_at, code_id),
            ).rowcount
            > 0
        )

    def invalidate_active(self, user_id: int, used_at: str) -> int:
        return self._write(
            """UPDATE password_recovery_codes SET used_at=?
               WHERE user_id=? AND used_at IS NULL""",
            (used_at, user_id),
        ).rowcount

    @staticmethod
    def _entity(row) -> PasswordRecoveryCodeEntity:
        return PasswordRecoveryCodeEntity(
            id=row["id"],
            user_id=row["user_id"],
            code_lookup=row["code_lookup"],
            code_hash=row["code_hash"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            used_at=row["used_at"],
        )
