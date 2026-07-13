from app.entities.session_entity import SessionEntity
from app.repositories.base_repository import BaseRepository


class SessionRepository(BaseRepository):
    def create(self, entity: SessionEntity):
        cursor = self._write("INSERT INTO sessions (user_id,token_hash,created_at,expires_at,last_activity_at,revoked_at,device_name) VALUES (?,?,?,?,?,?,?)", (entity.user_id,entity.token_hash,entity.created_at,entity.expires_at,entity.last_activity_at,entity.revoked_at,entity.device_name))
        entity.id=cursor.lastrowid; return entity
    def revoke(self, session_id: int, revoked_at: str):
        return self._write("UPDATE sessions SET revoked_at=? WHERE id=? AND revoked_at IS NULL",(revoked_at,session_id)).rowcount>0
    def find_by_id(self, session_id: int):
        r=self._fetch_one("SELECT * FROM sessions WHERE id=?",(session_id,)); return self._entity(r) if r else None
    @staticmethod
    def _entity(r):
        return SessionEntity(id=r["id"],user_id=r["user_id"],token_hash=r["token_hash"],created_at=r["created_at"],expires_at=r["expires_at"],last_activity_at=r["last_activity_at"],revoked_at=r["revoked_at"],device_name=r["device_name"])
