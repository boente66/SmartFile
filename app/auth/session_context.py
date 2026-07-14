from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.entities.organization_entity import OrganizationEntity
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.errors.auth_exceptions import AuthenticationError
from app.models.user_model import UserModel


ROLE_PERMISSIONS = {
    "OWNER": {"*"},
    "ADMIN": {"document.*", "folder.*", "tools.use", "organization.view", "organization.create", "organization.update", "member.view", "member.add", "member.create_user", "member.change_role", "member.deactivate", "member.remove", "profile.view", "profile.update", "session.view", "session.revoke", "cloud.view", "cloud.connect", "cloud.disconnect", "cloud.sync", "cloud.oauth.configure"},
    "EDITOR": {"document.create", "document.import", "document.update", "document.open", "document.view", "document.search", "folder.*", "tools.use", "organization.view", "organization.create", "profile.view", "profile.update", "session.view", "session.revoke", "cloud.view", "cloud.sync"},
    "VIEWER": {"document.view", "document.open", "document.search", "organization.view", "profile.view", "profile.update", "session.view", "session.revoke", "cloud.view"},
}


@dataclass(slots=True)
class SessionContext:
    current_user: UserModel | None = None
    session_id: int | None = None
    active_organization: OrganizationEntity | None = None
    memberships: list[OrganizationMemberEntity] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    login_at: datetime | None = None
    last_activity_at: datetime | None = None

    def is_authenticated(self) -> bool:
        return self.current_user is not None and self.session_id is not None

    def login(self, user, session_id, organization, memberships) -> None:
        self.current_user = user; self.session_id = session_id
        self.active_organization = organization; self.memberships = list(memberships)
        self.login_at = self.last_activity_at = datetime.now().astimezone()
        self._refresh_permissions()

    def logout(self) -> None:
        self.current_user = None; self.session_id = None; self.active_organization = None
        self.memberships.clear(); self.permissions.clear(); self.login_at = None; self.last_activity_at = None

    def set_active_organization(self, organization: OrganizationEntity) -> None:
        if not any(m.organization_id == organization.id and m.status == "ACTIVE" for m in self.memberships):
            raise AuthenticationError("Usuário não pertence a esta organização.")
        self.active_organization = organization; self._refresh_permissions()

    def has_permission(self, permission: str) -> bool:
        if "*" in self.permissions or permission in self.permissions:
            return True
        prefix = permission.split(".", 1)[0] + ".*"
        return prefix in self.permissions

    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            raise AuthenticationError("Permissão insuficiente para esta operação.")

    def _refresh_permissions(self) -> None:
        membership = next((m for m in self.memberships if m.organization_id == getattr(self.active_organization, "id", None)), None)
        self.permissions = set(ROLE_PERMISSIONS.get(membership.role, set())) if membership else set()
        if getattr(self.current_user, "is_superuser", False):
            self.permissions.add("*")
