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

    @classmethod
    def from_entity(cls, entity: UserEntity):
        return cls(
            id=int(entity.id), username=entity.username, email=entity.email,
            display_name=entity.display_name, phone=entity.phone,
            is_active=entity.is_active, is_superuser=entity.is_superuser,
            last_login_at=entity.last_login_at,
        )
