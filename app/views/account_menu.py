from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu


class AccountMenu(QMenu):
    def __init__(self,parent=None):
        super().__init__(parent); self.organization_menu=self.addMenu("Trocar organização"); self.addSeparator()
        self.change_password_action=QAction("Alterar senha",self); self.addAction(self.change_password_action)
        self.logout_action=QAction("Sair",self); self.addAction(self.logout_action)

    def set_organizations(self,organizations,active_id,callback):
        self.organization_menu.clear()
        for organization in organizations:
            action=self.organization_menu.addAction(organization.name); action.setCheckable(True); action.setChecked(organization.id==active_id); action.triggered.connect(lambda _checked=False,item=organization: callback(item))
