from datetime import datetime, timezone

from app.auth.password_service import PasswordService
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.user_entity import UserEntity
from app.errors.auth_exceptions import LastOwnerError, MembershipError
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService


class MemberService:
    ROLES={"OWNER","ADMIN","EDITOR","VIEWER"}
    def __init__(self,database,context):
        self.database=database; self.context=context; self.members=OrganizationMemberRepository(database=database); self.users=UserRepository(database=database); self.passwords=PasswordService(); self.audit=AuditService(database)

    def list_members(self,organization_id):
        self._require(organization_id,"member.view")
        return [(membership,self.users.find_by_id(membership.user_id)) for membership in self.members.find_by_organization(organization_id)]

    def add_existing(self,organization_id,login,role="VIEWER"):
        self._require(organization_id,"member.add"); self._role(role)
        user=self.users.find_by_login(login.strip())
        if not user: raise MembershipError("Usuário local não encontrado.")
        existing=self.members.find(organization_id,user.id)
        if existing:
            if existing.status=="ACTIVE": raise MembershipError("Usuário já pertence à organização.")
            existing.status="ACTIVE"; existing.role=role; existing.deactivated_at=None; existing.updated_at=self._now(); result=self.members.update(existing)
        else:
            now=self._now(); result=self.members.create(OrganizationMemberEntity(organization_id=organization_id,user_id=user.id,role=role,created_at=now,updated_at=now,joined_at=now,invited_by_user_id=self.context.current_user.id))
        self._audit("MEMBER_ADDED",organization_id,user.id,f"Membro adicionado: {user.username} ({role})")
        return result

    def create_user(self,organization_id,display_name,username,password,email=None,role="VIEWER"):
        self._require(organization_id,"member.create_user"); self._role(role)
        if self.users.find_by_username(username.strip()): raise MembershipError("Nome de usuário já cadastrado.")
        if email and self.users.find_by_email(email.strip().lower()): raise MembershipError("E-mail já cadastrado.")
        if len(password)<8: raise MembershipError("A senha temporária deve possuir pelo menos 8 caracteres.")
        now=self._now()
        with self.database.transaction():
            user=self.users.create(UserEntity(username=username.strip(),email=email.strip().lower() if email else None,display_name=" ".join(display_name.split()),password_hash=self.passwords.hash_password(password),must_change_password=True,created_at=now,updated_at=now))
            membership=self.members.create(OrganizationMemberEntity(organization_id=organization_id,user_id=user.id,role=role,created_at=now,updated_at=now,joined_at=now,invited_by_user_id=self.context.current_user.id))
            self._audit("MEMBER_USER_CREATED",organization_id,user.id,f"Usuário local criado: {user.username} ({role})")
        return user,membership

    def change_role(self,organization_id,user_id,new_role):
        self._require(organization_id,"member.change_role"); self._role(new_role)
        membership=self._member(organization_id,user_id); actor=self._member(organization_id,self.context.current_user.id)
        if new_role=="OWNER" and membership.role!="OWNER": raise MembershipError("Use a transferência de propriedade para definir um novo OWNER.")
        if actor.role=="ADMIN" and (membership.role=="OWNER" or new_role in {"OWNER","ADMIN"}): raise MembershipError("ADMIN não pode alterar OWNER ou promover para ADMIN/OWNER.")
        if membership.role=="OWNER" and new_role!="OWNER" and self.members.count_active_owners(organization_id)<=1: raise LastOwnerError("A organização deve manter pelo menos um OWNER.")
        if user_id==self.context.current_user.id and new_role=="OWNER" and actor.role!="OWNER": raise MembershipError("Não é permitido elevar o próprio papel.")
        membership.role=new_role; membership.updated_at=self._now(); result=self.members.update(membership); self._audit("MEMBER_ROLE_CHANGED",organization_id,user_id,f"Papel alterado para {new_role}"); self._refresh(); return result

    def deactivate(self,organization_id,user_id):
        self._require(organization_id,"member.deactivate"); membership=self._member(organization_id,user_id)
        if membership.role=="OWNER" and self.members.count_active_owners(organization_id)<=1: raise LastOwnerError("O último OWNER não pode ser desativado.")
        membership.status="INACTIVE"; membership.deactivated_at=membership.updated_at=self._now(); self.members.update(membership); self._audit("MEMBER_DEACTIVATED",organization_id,user_id,"Vínculo desativado"); self._refresh()

    def reactivate(self,organization_id,user_id):
        self._require(organization_id,"member.add"); membership=self.members.find(organization_id,user_id)
        if not membership or membership.status=="ACTIVE": raise MembershipError("Vínculo inativo não encontrado.")
        membership.status="ACTIVE"; membership.deactivated_at=None; membership.updated_at=self._now(); self.members.update(membership); self._audit("MEMBER_REACTIVATED",organization_id,user_id,"Vínculo reativado"); return membership

    def remove(self,organization_id,user_id):
        self._require(organization_id,"member.remove"); membership=self._member(organization_id,user_id); actor=self._member(organization_id,self.context.current_user.id)
        if actor.role=="ADMIN" and membership.role=="OWNER": raise MembershipError("ADMIN não pode remover OWNER.")
        if membership.role=="OWNER" and self.members.count_active_owners(organization_id)<=1: raise LastOwnerError("O último OWNER não pode sair ou ser removido.")
        membership.status="REMOVED"; membership.deactivated_at=membership.updated_at=self._now(); self.members.update(membership); self._audit("MEMBER_REMOVED",organization_id,user_id,"Membro removido"); self._refresh()

    def transfer_ownership(self,organization_id,new_owner_id,current_password,previous_role="ADMIN"):
        self._require(organization_id,"organization.transfer_ownership")
        actor=self._member(organization_id,self.context.current_user.id)
        if actor.role!="OWNER": raise MembershipError("Somente OWNER pode transferir a propriedade.")
        if new_owner_id==self.context.current_user.id: raise MembershipError("Selecione outro membro para receber a propriedade.")
        user=self.users.find_by_id(self.context.current_user.id)
        if not self.passwords.verify_password(current_password,user.password_hash): raise MembershipError("Senha atual incorreta.")
        target=self._member(organization_id,new_owner_id)
        if target.status!="ACTIVE": raise MembershipError("O novo proprietário deve estar ativo.")
        if previous_role not in {"ADMIN","EDITOR","VIEWER"}: raise MembershipError("Papel anterior inválido.")
        now=self._now()
        with self.database.transaction():
            target.role="OWNER"; target.updated_at=now; self.members.update(target)
            actor.role=previous_role; actor.updated_at=now; self.members.update(actor)
            self._audit("OWNERSHIP_TRANSFERRED",organization_id,new_owner_id,f"Propriedade transferida; proprietário anterior agora é {previous_role}")
        self._refresh(); return target

    def _require(self,organization_id,permission):
        if organization_id!=getattr(self.context.active_organization,"id",None): raise MembershipError("Ative a organização antes de gerenciar membros.")
        self.context.require_permission(permission)
    def _member(self,organization_id,user_id):
        member=self.members.find(organization_id,user_id)
        if not member or member.status!="ACTIVE": raise MembershipError("Membro ativo não encontrado.")
        return member
    def _role(self,role):
        if role not in self.ROLES: raise MembershipError("Papel inválido.")
    def _audit(self,action,organization_id,target_id,description): self.audit.record(action,user_id=self.context.current_user.id,organization_id=organization_id,target_type="user",target_id=target_id,description=description)
    def _refresh(self): self.context.memberships=self.members.find_by_user(self.context.current_user.id); self.context._refresh_permissions()
    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
