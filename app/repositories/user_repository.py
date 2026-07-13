from app.entities.user_entity import UserEntity
from app.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository):
    def create(self, entity: UserEntity) -> UserEntity:
        cursor = self._write(
            """INSERT INTO users (username,email,display_name,phone,password_hash,is_active,is_superuser,
            failed_login_attempts,locked_until,last_login_at,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", self._values(entity)
        )
        entity.id = cursor.lastrowid; return entity

    def update(self, entity: UserEntity) -> UserEntity:
        self._write(
            """UPDATE users SET username=?,email=?,display_name=?,phone=?,password_hash=?,is_active=?,
            is_superuser=?,failed_login_attempts=?,locked_until=?,last_login_at=?,created_at=?,updated_at=? WHERE id=?""",
            (*self._values(entity), entity.id),
        ); return entity

    def find_by_id(self, user_id: int):
        row = self._fetch_one("SELECT * FROM users WHERE id=?", (user_id,)); return self._entity(row) if row else None

    def find_by_login(self, login: str):
        row = self._fetch_one("SELECT * FROM users WHERE lower(username)=lower(?) OR lower(email)=lower(?)", (login, login))
        return self._entity(row) if row else None

    def find_by_username(self, username: str):
        row = self._fetch_one("SELECT * FROM users WHERE lower(username)=lower(?)", (username,)); return self._entity(row) if row else None

    def find_by_email(self, email: str):
        row = self._fetch_one("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)); return self._entity(row) if row else None

    def count(self) -> int:
        return int(self._fetch_one("SELECT COUNT(*) total FROM users")["total"])

    @staticmethod
    def _values(e):
        return (e.username,e.email,e.display_name,e.phone,e.password_hash,int(e.is_active),int(e.is_superuser),e.failed_login_attempts,e.locked_until,e.last_login_at,e.created_at,e.updated_at)

    @staticmethod
    def _entity(r):
        return UserEntity(id=r["id"],username=r["username"],email=r["email"],display_name=r["display_name"],phone=r["phone"],password_hash=r["password_hash"],is_active=bool(r["is_active"]),is_superuser=bool(r["is_superuser"]),failed_login_attempts=r["failed_login_attempts"],locked_until=r["locked_until"],last_login_at=r["last_login_at"],created_at=r["created_at"],updated_at=r["updated_at"])
