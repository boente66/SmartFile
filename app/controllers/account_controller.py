from PyQt6.QtWidgets import QDialog, QMessageBox

from app.views.account_menu import AccountMenu
from app.views.change_password_dialog import ChangePasswordDialog


class AccountController:
    def __init__(self,main_view,auth_service,app_controller,logout_callback):
        self.main_view=main_view; self.auth=auth_service; self.app_controller=app_controller; self.logout_callback=logout_callback
        self.menu=AccountMenu(main_view); self.menu.change_password_action.triggered.connect(self.change_password); self.menu.logout_action.triggered.connect(self.logout_callback)
        self.menu.aboutToShow.connect(self.refresh)
        self.refresh()

    def refresh(self):
        context=self.auth.session_context; user=context.current_user
        organizations=[]
        for member in context.memberships:
            organization=self.auth.organizations.repository.find_by_id(member.organization_id)
            if organization and organization.status=="ACTIVE": organizations.append(organization)
        self.menu.set_organizations(organizations,getattr(context.active_organization,"id",None),self.switch_organization)
        self.main_view.set_account(user.display_name if user else "Conta",self.menu)

    def switch_organization(self,organization):
        try:
            self.auth.session_context.set_active_organization(organization); self.auth.organizations.set_active(organization.id)
            if self.app_controller.document_controller: self.app_controller.document_controller.activate()
            self.refresh()
        except Exception as exc: QMessageBox.warning(self.main_view,"Organização",str(exc))

    def change_password(self):
        dialog=ChangePasswordDialog(self.main_view)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        try:
            self.auth.change_password(dialog.current.text(),dialog.new.text(),dialog.confirmation.text()); QMessageBox.information(self.main_view,"Senha","Senha alterada com sucesso.")
        except Exception as exc: QMessageBox.warning(self.main_view,"Senha",str(exc))
