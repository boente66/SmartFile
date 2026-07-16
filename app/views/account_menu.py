from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu

from app.ui.icon_provider import IconProvider


class AccountMenu(QMenu):
    def __init__(self,parent=None):
        super().__init__(parent); self.profile_action=QAction("Meu Perfil",self); self.addAction(self.profile_action); self.change_password_action=QAction("Alterar senha",self); self.addAction(self.change_password_action); self.organization_menu=self.addMenu("Trocar organização"); self.manage_organizations_action=QAction("Gerenciar organizações",self); self.addAction(self.manage_organizations_action); self.members_action=QAction("Usuários e permissões",self); self.addAction(self.members_action); self.sessions_action=QAction("Sessões",self); self.addAction(self.sessions_action); self.provider_settings_action=QAction("Configurar provedor",self); self.addAction(self.provider_settings_action); self.backup_action=QAction(IconProvider.icon("save"),"Criar backup ZIP",self); self.addAction(self.backup_action); self.settings_action=QAction("Configurações",self); self.addAction(self.settings_action); self.addSeparator(); self.delete_account_action=QAction("Excluir minha conta",self); self.addAction(self.delete_account_action); self.logout_action=QAction("Sair",self); self.addAction(self.logout_action)
    def set_organizations(self,organizations,active_id,callback):
        self.organization_menu.clear()
        for organization in organizations:
            action=self.organization_menu.addAction(organization.name); action.setCheckable(True); action.setChecked(organization.id==active_id); action.triggered.connect(lambda _checked=False,item=organization: callback(item))
    def apply_permissions(self,context):
        self.manage_organizations_action.setVisible(context.has_permission("organization.view")); self.members_action.setVisible(context.has_permission("member.view")); self.profile_action.setVisible(context.has_permission("profile.view")); self.sessions_action.setVisible(context.has_permission("session.view")); self.provider_settings_action.setVisible(context.is_system_admin()); self.backup_action.setVisible(context.is_system_admin()); self.settings_action.setVisible(False)
