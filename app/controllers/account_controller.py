from PyQt6.QtWidgets import QDialog,QInputDialog,QLineEdit,QMessageBox

from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.services.member_service import MemberService
from app.services.organization_admin_service import OrganizationAdminService
from app.services.profile_service import ProfileService
from app.views.account_menu import AccountMenu
from app.views.change_password_dialog import ChangePasswordDialog
from app.views.cloud_api_settings_dialog import CloudApiSettingsDialog
from app.views.delete_account_dialog import DeleteAccountDialog
from app.views.member_management_view import MemberManagementView
from app.views.organization_dialog import OrganizationDialog
from app.views.organization_management_view import OrganizationManagementView
from app.views.profile_dialog import ProfileDialog


class AccountController:
    def __init__(self,main_view,auth_service,app_controller,logout_callback):
        self.main_view=main_view; self.auth=auth_service; self.app_controller=app_controller; self.logout_callback=logout_callback; self.organizations=OrganizationAdminService(auth_service.database,auth_service.session_context); self.members=MemberService(auth_service.database,auth_service.session_context); self.profile=ProfileService(auth_service.database,auth_service.session_context)
        self.menu=AccountMenu(main_view); self.menu.profile_action.triggered.connect(self.edit_profile); self.menu.change_password_action.triggered.connect(self.change_password); self.menu.manage_organizations_action.triggered.connect(self.manage_organizations); self.menu.members_action.triggered.connect(lambda:self.manage_members(self.auth.session_context.active_organization.id)); self.menu.sessions_action.triggered.connect(self.show_sessions); self.menu.provider_settings_action.triggered.connect(self.configure_provider); self.menu.delete_account_action.triggered.connect(self.delete_account); self.menu.logout_action.triggered.connect(self.logout_callback); self.menu.aboutToShow.connect(self.refresh); self.refresh()

    def refresh(self):
        context=self.auth.session_context; user=context.current_user; organizations=[o for o,_,_ in self.organizations.list_for_current_user()]; self.menu.set_organizations(organizations,getattr(context.active_organization,"id",None),self.switch_organization); self.menu.apply_permissions(context); self.main_view.set_account(user.display_name if user else "Conta",self.menu)

    def switch_organization(self,organization):
        try:
            self.organizations.activate(organization.id)
            if self.app_controller.document_controller: self.app_controller.document_controller.activate()
            self.refresh()
        except Exception as exc: QMessageBox.warning(self.main_view,"Organização",str(exc))

    def change_password(self):
        dialog=ChangePasswordDialog(self.main_view)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try: self.auth.change_password(dialog.current.text(),dialog.new.text(),dialog.confirmation.text()); QMessageBox.information(self.main_view,"Senha","Senha alterada com sucesso.")
        except Exception as exc: QMessageBox.warning(self.main_view,"Senha",str(exc))

    def edit_profile(self):
        dialog=ProfileDialog(self.auth.session_context.current_user,self.main_view)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try: self.profile.update(dialog.name.text(),dialog.email.text() or None,dialog.phone.text() or None,dialog.avatar_path,dialog.remove_avatar); self.refresh(); QMessageBox.information(self.main_view,"Perfil","Perfil atualizado.")
        except Exception as exc: QMessageBox.warning(self.main_view,"Perfil",str(exc))

    def manage_organizations(self):
        view=OrganizationManagementView(self.main_view); self._organization_view=view
        view.create_requested.connect(lambda:self._create_organization(view)); view.open_requested.connect(lambda oid:(self.switch_organization(self.auth.organizations.repository.find_by_id(oid)),view.accept())); view.edit_requested.connect(lambda oid:self._edit_organization(view,oid)); view.duplicate_requested.connect(lambda oid:self._duplicate_organization(view,oid)); view.archive_requested.connect(lambda oid:self._archive_organization(view,oid)); view.members_requested.connect(self.manage_members); self._reload_organizations(view); view.exec()

    def _reload_organizations(self,view): view.set_items(self.organizations.list_for_current_user(include_archived=True))
    def _create_organization(self,view):
        dialog=OrganizationDialog(view)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try: self.organizations.create(**dialog.values()); self._reload_organizations(view); self.refresh()
        except Exception as exc: QMessageBox.warning(view,"Organização",str(exc))
    def _edit_organization(self,view,oid):
        organization=self.auth.organizations.repository.find_by_id(oid); dialog=OrganizationDialog(view,organization,False)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try: values=dialog.values(); self.organizations.update(oid,values["name"],values["description"],values["icon"],values["color"]); self._reload_organizations(view); self.refresh()
        except Exception as exc: QMessageBox.warning(view,"Organização",str(exc))
    def _duplicate_organization(self,view,oid):
        name,ok=QInputDialog.getText(view,"Duplicar estrutura","Nome da nova organização:")
        if ok:
            try:self.organizations.duplicate(oid,name); self._reload_organizations(view); self.refresh()
            except Exception as exc: QMessageBox.warning(view,"Organização",str(exc))
    def _archive_organization(self,view,oid):
        organization=self.auth.organizations.repository.find_by_id(oid); stats=self.organizations.statistics(oid); typed,ok=QInputDialog.getText(view,"Arquivar organização",f"Documentos: {stats['documents']} | Pastas: {stats['folders']} | Membros: {stats['members']}\nDigite exatamente '{organization.name}':")
        if ok:
            try:self.organizations.archive(oid,typed); self._reload_organizations(view); self.refresh()
            except Exception as exc: QMessageBox.warning(view,"Organização",str(exc))

    def manage_members(self,organization_id):
        if organization_id!=self.auth.session_context.active_organization.id: QMessageBox.information(self.main_view,"Organização","Ative a organização antes de gerenciar seus membros."); return
        view=MemberManagementView(self.main_view); self._member_view=view; reload=lambda:view.set_members(self.members.list_members(organization_id)); view.add_requested.connect(lambda:self._add_member(view,organization_id,reload)); view.create_requested.connect(lambda:self._create_member(view,organization_id,reload)); view.role_requested.connect(lambda uid:self._change_role(view,organization_id,uid,reload)); view.deactivate_requested.connect(lambda uid:self._member_action(view,lambda:self.members.deactivate(organization_id,uid),reload)); view.remove_requested.connect(lambda uid:self._member_action(view,lambda:self.members.remove(organization_id,uid),reload)); view.transfer_requested.connect(lambda uid:self._transfer(view,organization_id,uid,reload)); reload(); view.exec()
    def _add_member(self,view,oid,reload):
        login,ok=QInputDialog.getText(view,"Adicionar usuário","Username ou e-mail:"); role,rok=QInputDialog.getItem(view,"Papel","Papel:",["VIEWER","EDITOR","ADMIN"],0,False)
        if ok and rok:self._member_action(view,lambda:self.members.add_existing(oid,login,role),reload)
    def _create_member(self,view,oid,reload):
        name,ok=QInputDialog.getText(view,"Novo usuário","Nome completo:"); username,uok=QInputDialog.getText(view,"Novo usuário","Username:"); password,pok=QInputDialog.getText(view,"Senha temporária","Senha:",QLineEdit.EchoMode.Password); role,rok=QInputDialog.getItem(view,"Papel","Papel:",["VIEWER","EDITOR","ADMIN"],0,False)
        if all((ok,uok,pok,rok)):self._member_action(view,lambda:self.members.create_user(oid,name,username,password,role=role),reload)
    def _change_role(self,view,oid,uid,reload):
        role,ok=QInputDialog.getItem(view,"Alterar papel","Novo papel:",["VIEWER","EDITOR","ADMIN","OWNER"],0,False)
        if ok:self._member_action(view,lambda:self.members.change_role(oid,uid,role),reload)
    def _transfer(self,view,oid,uid,reload):
        password,ok=QInputDialog.getText(view,"Transferir propriedade","Confirme sua senha atual:",QLineEdit.EchoMode.Password)
        if ok:self._member_action(view,lambda:self.members.transfer_ownership(oid,uid,password),reload)
    @staticmethod
    def _member_action(view,action,reload):
        try:action(); reload()
        except Exception as exc:QMessageBox.warning(view,"Usuários e permissões",str(exc))
    def show_sessions(self):
        sessions=self.profile.active_sessions(); text="\n".join(f"{row['device_name']} — {row['created_at']}" for row in sessions) or "Nenhuma sessão ativa."; result=QMessageBox.question(self.main_view,"Sessões",text+"\n\nEncerrar as outras sessões?")
        if result==QMessageBox.StandardButton.Yes:self.profile.revoke_other_sessions()

    def configure_provider(self):
        try:
            if not self.auth.session_context.is_system_admin():
                raise PermissionError("Somente o administrador do sistema pode configurar provedores OAuth.")
            CloudApiSettingsDialog(
                CloudOAuthConfigService(self.auth.database),
                self.main_view,
            ).exec()
            if self.app_controller.document_controller:
                self.app_controller.document_controller.activate()
        except Exception as exc:
            QMessageBox.warning(self.main_view,"Configurar provedor",str(exc))

    def delete_account(self):
        dialog=DeleteAccountDialog(self.main_view)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            password,confirmation=dialog.values(); self.auth.delete_current_account(password,confirmation)
            QMessageBox.information(self.main_view,"Conta excluída","Sua conta foi excluída e todas as sessões foram encerradas.")
            self.logout_callback()
        except Exception as exc:
            QMessageBox.warning(self.main_view,"Excluir minha conta",str(exc))
