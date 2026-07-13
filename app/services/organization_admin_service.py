from datetime import datetime, timezone

from app.entities.organization_member_entity import OrganizationMemberEntity
from app.errors.auth_exceptions import AdministrationError
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.services.audit_service import AuditService
from app.services.folder_service import FolderService
from app.services.folder_template_service import FolderTemplateService
from app.services.organization_service import OrganizationService
from app.cloud.cloud_manager import CloudManager


class OrganizationAdminService:
    def __init__(self,database,session_context):
        self.database=database; self.context=session_context
        self.organizations=OrganizationService(database); self.members=OrganizationMemberRepository(database=database)
        self.folders=FolderService(database); self.templates=FolderTemplateService(self.folders); self.audit=AuditService(database)
        self.cloud=CloudManager(database)

    def list_for_current_user(self, include_archived=False):
        linked={m.organization_id:m for m in self.members.find_by_user(self.context.current_user.id,active_only=False)}
        organizations=self.organizations.repository.find_all()
        if include_archived: organizations += self.organizations.repository.find_archived()
        return [(o,linked[o.id],self.statistics(o.id)) for o in organizations if o.id in linked]

    def statistics(self,organization_id):
        cloud=self.organizations.repository.cloud_summary(organization_id)
        return {"documents":self.organizations.repository.count_documents(organization_id),"folders":self.organizations.repository.count_folders(organization_id),"members":self.members.count_active(organization_id),"cloud":cloud["sync_mode"] if cloud else "LOCAL","last_activity":cloud["last_sync"] if cloud else None}

    def create(self,name,description=None,icon="organization",color="#2563eb",template="EMPTY",activate=False):
        self.context.require_permission("organization.create")
        if any(o.name.casefold()==name.strip().casefold() for o,_,_ in self.list_for_current_user()): raise AdministrationError("Você já possui uma organização com esse nome.")
        now=self._now()
        with self.database.transaction():
            organization=self.organizations.create(name,description); organization.icon=icon; organization.color=color; self.organizations.repository.update(organization)
            membership=self.members.create(OrganizationMemberEntity(organization_id=organization.id,user_id=self.context.current_user.id,role="OWNER",created_at=now,updated_at=now,joined_at=now))
            self.templates.create_template_folders(organization.id,template)
            self.cloud.settings(organization.id)
            self.audit.record("ORGANIZATION_CREATED",user_id=self.context.current_user.id,organization_id=organization.id,target_type="organization",target_id=organization.id,description=f"Organização criada: {organization.name}")
        self.context.memberships.append(membership)
        if activate: self.activate(organization.id)
        return organization

    def update(self,organization_id,name,description=None,icon=None,color=None):
        self._require_for(organization_id,"organization.update")
        organization=self.organizations.update(organization_id,name,description)
        if icon is not None: organization.icon=icon
        if color is not None: organization.color=color
        organization=self.organizations.repository.update(organization)
        self.audit.record("ORGANIZATION_UPDATED",user_id=self.context.current_user.id,organization_id=organization_id,target_type="organization",target_id=organization_id,description=f"Organização editada: {organization.name}")
        return organization

    def duplicate(self,organization_id,new_name,activate=False):
        self._require_for(organization_id,"organization.create")
        source=self.organizations.repository.find_by_id(organization_id)
        with self.database.transaction():
            target=self.organizations.create(new_name,source.description); target.icon=source.icon; target.color=source.color; self.organizations.repository.update(target)
            now=self._now(); membership=self.members.create(OrganizationMemberEntity(organization_id=target.id,user_id=self.context.current_user.id,role="OWNER",created_at=now,updated_at=now,joined_at=now))
            mapping={}
            remaining=list(self.folders.list_folders(organization_id))
            while remaining:
                progressed=False
                for folder in remaining[:]:
                    if folder.parent_id is None or folder.parent_id in mapping:
                        created=self.folders.create(target.id,folder.name,mapping.get(folder.parent_id)); mapping[folder.id]=created.id; remaining.remove(folder); progressed=True
                if not progressed: raise AdministrationError("Estrutura de pastas inválida.")
            self.cloud.settings(target.id)
            self.audit.record("ORGANIZATION_DUPLICATED",user_id=self.context.current_user.id,organization_id=target.id,target_type="organization",target_id=target.id,description=f"Estrutura duplicada de {source.name}")
        self.context.memberships.append(membership)
        if activate: self.activate(target.id)
        return target

    def archive(self,organization_id,typed_name):
        self._require_for(organization_id,"organization.archive")
        organization=self.organizations.repository.find_by_id(organization_id)
        membership=self.members.find(organization_id,self.context.current_user.id)
        if membership.role!="OWNER": raise AdministrationError("Somente OWNER pode arquivar a organização.")
        if typed_name != organization.name: raise AdministrationError("Digite exatamente o nome da organização para confirmar.")
        if len(self.members.find_by_user(self.context.current_user.id)) <= 1: raise AdministrationError("Não é possível arquivar sua única organização ativa.")
        if self.organizations.repository.has_sync_in_progress(organization_id): raise AdministrationError("Existe sincronização em andamento.")
        now=self._now(); self.organizations.repository.archive(organization_id,now)
        self.audit.record("ORGANIZATION_ARCHIVED",user_id=self.context.current_user.id,organization_id=organization_id,target_type="organization",target_id=organization_id,description=f"Organização arquivada: {organization.name}")
        if getattr(self.context.active_organization,"id",None)==organization_id:
            replacement=next(o for o,m,_ in self.list_for_current_user() if o.id!=organization_id); self.activate(replacement.id)

    def activate(self,organization_id):
        organization=self.organizations.repository.find_by_id(organization_id); self.context.set_active_organization(organization); self.organizations.set_active(organization_id)
        self.audit.record("ORGANIZATION_SWITCHED",user_id=self.context.current_user.id,organization_id=organization_id,target_type="organization",target_id=organization_id,description=f"Organização ativa: {organization.name}")
        return organization

    def _require_for(self,organization_id,permission):
        if getattr(self.context.active_organization,"id",None)==organization_id: self.context.require_permission(permission); return
        membership=self.members.find(organization_id,self.context.current_user.id)
        if not membership or membership.status!="ACTIVE": raise AdministrationError("Usuário não pertence à organização.")
        from app.auth.session_context import ROLE_PERMISSIONS
        permissions=ROLE_PERMISSIONS.get(membership.role,set())
        if "*" not in permissions and permission not in permissions and permission.split('.')[0]+'.*' not in permissions: raise AdministrationError("Permissão insuficiente.")

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
