from dataclasses import dataclass

from app.entities.user_entity import UserEntity


@dataclass(frozen=True, slots=True)
class UserModel:
    id: int
    username: str
    email: str | None
    display_name: str
    phone: str | None
    is_active: bool
    is_superuser: bool
    last_login_at: str | None
    avatar_path: str | None = None
    avatar_initials: str | None = None
    avatar_color: str | None = None
    must_change_password: bool = False

    @classmethod
    def from_entity(cls, entity: UserEntity):
        return cls(
            id=int(entity.id), username=entity.username, email=entity.email,
            display_name=entity.display_name, phone=entity.phone,
            is_active=entity.is_active, is_superuser=entity.is_superuser,
            last_login_at=entity.last_login_at,
            avatar_path=entity.avatar_path, avatar_initials=entity.avatar_initials,
            avatar_color=entity.avatar_color, must_change_password=entity.must_change_password,
        )
