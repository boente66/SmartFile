from dataclasses import dataclass


@dataclass(slots=True)
class UserEntity:
    id: int | None = None
    username: str = ""
    email: str | None = None
    display_name: str = ""
    phone: str | None = None
    password_hash: str = ""
    is_active: bool = True
    is_superuser: bool = False
    failed_login_attempts: int = 0
    locked_until: str | None = None
    last_login_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    avatar_path: str | None = None
    avatar_initials: str | None = None
    avatar_color: str | None = None
    must_change_password: bool = False
