from dataclasses import dataclass


@dataclass(slots=True)
class SessionEntity:
    id: int | None = None
    user_id: int = 0
    token_hash: str | None = None
    created_at: str = ""
    expires_at: str | None = None
    last_activity_at: str | None = None
    revoked_at: str | None = None
    device_name: str | None = None
