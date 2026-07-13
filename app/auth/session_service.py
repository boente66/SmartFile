import hashlib
import platform
import secrets
from datetime import datetime, timedelta, timezone

from app.entities.session_entity import SessionEntity
from app.repositories.session_repository import SessionRepository


class SessionService:
    def __init__(self, repository: SessionRepository):
        self.repository = repository

    def create(self, user_id: int, remember: bool = False) -> SessionEntity:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        return self.repository.create(SessionEntity(
            user_id=user_id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
            created_at=now.isoformat(), expires_at=(now + timedelta(days=30 if remember else 1)).isoformat(),
            last_activity_at=now.isoformat(), device_name=platform.node() or "SmartFile",
        ))

    def revoke(self, session_id: int) -> bool:
        return self.repository.revoke(session_id, datetime.now(timezone.utc).isoformat())
