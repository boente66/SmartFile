from datetime import datetime, timezone
from pathlib import Path

from app.errors.auth_exceptions import EmailAlreadyExistsError
from app.models.user_model import UserModel
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.avatar_service import AvatarService


class ProfileService:
    def __init__(self,database,context):
        self.context=context; self.users=UserRepository(database=database); self.sessions=SessionRepository(database=database); self.avatars=AvatarService(database); self.audit=AuditService(database)

    def update(self,display_name,email=None,phone=None,avatar_source=None,remove_avatar=False):
        self.context.require_permission("profile.update"); user=self.users.find_by_id(self.context.current_user.id)
        previous_avatar=user.avatar_path
        name=" ".join(display_name.split())
        if not name: raise ValueError("Informe o nome completo.")
        normalized=email.strip().lower() if email else None; duplicate=self.users.find_by_email(normalized) if normalized else None
        if duplicate and duplicate.id!=user.id: raise EmailAlreadyExistsError("E-mail já cadastrado.")
        if remove_avatar: user.avatar_path=None
        elif avatar_source: user.avatar_path=self.avatars.store(avatar_source)
        user.display_name=name; user.email=normalized; user.phone=phone.strip() if phone else None; user.avatar_initials=self.avatars.initials(name); user.avatar_color=user.avatar_color or "#2563eb"; user.updated_at=datetime.now(timezone.utc).isoformat(); self.users.update(user)
        self.context.current_user=UserModel.from_entity(user); self.audit.record("PROFILE_UPDATED",user_id=user.id,organization_id=getattr(self.context.active_organization,"id",None),target_type="user",target_id=user.id,description="Perfil atualizado")
        if previous_avatar != user.avatar_path: self.audit.record("AVATAR_UPDATED",user_id=user.id,organization_id=getattr(self.context.active_organization,"id",None),target_type="user",target_id=user.id,description="Avatar atualizado")
        return self.context.current_user

    def active_sessions(self):
        return self.sessions.find_active_by_user(self.context.current_user.id)

    def revoke_other_sessions(self):
        now=datetime.now(timezone.utc).isoformat(); self.sessions.revoke_others(self.context.current_user.id,self.context.session_id,now); self.audit.record("OTHER_SESSIONS_REVOKED",user_id=self.context.current_user.id,organization_id=getattr(self.context.active_organization,"id",None),target_type="session",description="Outras sessões revogadas")
