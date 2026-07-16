import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

from app.controllers.app_controller import AppController
from app.controllers.auth_controller import AuthController
from app.database.database import Database
from app.models.registration_request import RegistrationRequest
from app.views.first_user_setup_view import FirstUserSetupView
from app.views.login_view import LoginView
from app.views.main_view import MainView
from app.views.account_menu import AccountMenu
from app.views.delete_account_dialog import DeleteAccountDialog

_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _request():
    return RegistrationRequest(
        display_name="Pessoa", username="pessoa", email="pessoa@example.com",
        phone=None, password="senha-segura", password_confirmation="senha-segura",
        template_code="PERSONAL",
    )


def test_login_and_setup_password_fields_are_protected():
    _app(); login = LoginView(); setup = FirstUserSetupView()
    assert login.password_edit.echoMode() == QLineEdit.EchoMode.Password
    assert setup.password.echoMode() == QLineEdit.EchoMode.Password
    assert setup.confirmation.echoMode() == QLineEdit.EchoMode.Password
    assert setup.templates.checkedButton().property("templateCode") == "PERSONAL"
    login.close(); setup.close()


def test_login_exposes_local_registration_and_registration_can_return():
    app = _app(); login = LoginView(allow_registration=True)
    requested = []
    login.create_account_requested.connect(lambda: requested.append(True))
    create_button = next(
        button for button in login.findChildren(QPushButton)
        if button.text() == "Criar conta"
    )
    create_button.click(); app.processEvents()
    assert requested == [True]

    setup = FirstUserSetupView(first_user=False)
    returned = []; setup.back_requested.connect(lambda: returned.append(True))
    back_button = next(
        button for button in setup.findChildren(QPushButton)
        if button.text() == "Voltar ao login"
    )
    back_button.click(); app.processEvents()
    assert returned == [True]
    login.close(); setup.close()


def test_auth_controller_opens_additional_registration_from_login(tmp_path: Path):
    app = _app(); database = Database(str(tmp_path / "smartfile.db"))
    controller = AuthController(app, database)
    controller.service.register_first_user(_request()); controller.service.logout()
    controller.start(); app.processEvents()
    assert isinstance(controller.auth_view, LoginView)
    controller.auth_view.create_account_requested.emit(); app.processEvents()
    assert isinstance(controller.auth_view, FirstUserSetupView)
    assert controller.auth_view.first_user is False
    controller.auth_view.close()


def test_main_view_is_not_created_before_authentication(tmp_path: Path):
    app = _app(); controller = AuthController(app, Database(str(tmp_path / "smartfile.db")))
    controller.start(); app.processEvents()
    assert isinstance(controller.auth_view, FirstUserSetupView)
    assert controller.main_view is None
    assert controller.session_context.is_authenticated() is False
    controller.auth_view.close()


def test_successful_first_setup_reaches_protected_application_callback(tmp_path: Path):
    app = _app(); controller = AuthController(app, Database(str(tmp_path / "smartfile.db")))
    opened = []
    controller._open_application = lambda: opened.append(controller.session_context.is_authenticated())
    controller.start(); controller._register(_request())
    assert controller.auth_view.stack.currentIndex() == 3
    controller.auth_view.enter_requested.emit()
    assert opened == [True]
    controller.auth_view.close()


def test_authenticated_app_keeps_existing_modules_registered(tmp_path: Path):
    app = _app(); database = Database(str(tmp_path / "smartfile.db"))
    auth = AuthController(app, database); auth.service.register_first_user(_request())
    main = MainView(); controller = AppController(main, auth.session_context, database); controller.start()
    assert {"documents", "converter", "pdf", "pdf_viewer", "scanner"} <= set(main.workspace.list_views())
    main.close()


def test_wizard_navigates_validates_and_builds_summary():
    app=_app(); wizard=FirstUserSetupView()
    wizard.next_step(); assert wizard.stack.currentIndex()==0 and wizard.error_label.text()
    wizard.display_name.setText("Pessoa Teste"); wizard.username.setText("pessoa"); wizard.password.setText("senha-segura"); wizard.confirmation.setText("senha-segura")
    wizard.next_step(); assert wizard.stack.currentIndex()==1
    wizard.organization_name.setText("Empresa ABC")
    wizard.next_step(); assert wizard.stack.currentIndex()==2
    wizard.templates.buttons()[2].setChecked(True)
    wizard.next_step(); assert wizard.stack.currentIndex()==3 and "Empresa ABC" in wizard.summary.text() and "OWNER" in wizard.summary.text()
    wizard.previous_step(); assert wizard.stack.currentIndex()==2
    wizard.close(); app.processEvents()


def test_registration_screen_follows_four_step_model():
    app=_app(); wizard=FirstUserSetupView()
    assert wizard.step_indicator.CAPTIONS == ("Dados pessoais","Organização","Template","Resumo")
    assert wizard.avatar_preview.width() == wizard.avatar_preview.height() == 170
    assert wizard.top_back_button.text().endswith("Voltar ao login")
    assert wizard.next_button.text().startswith("Continuar")
    wizard.resize(940,650); wizard.show(); app.processEvents()
    assert wizard.scroll.verticalScrollBar().maximum() > 0
    wizard.close()


def test_account_menu_hides_member_management_without_permission():
    _app(); menu=AccountMenu(); from app.auth.session_context import SessionContext
    context=SessionContext(); context.permissions={"organization.view","profile.view","session.view"}; menu.apply_permissions(context)
    assert menu.manage_organizations_action.isVisible(); assert menu.members_action.isVisible() is False
    assert menu.provider_settings_action.isVisible() is False
    assert menu.backup_action.isVisible() is False
    assert menu.delete_account_action.isVisible()


def test_provider_configuration_is_visible_only_with_administrative_permission():
    _app(); menu=AccountMenu(); from app.auth.session_context import SessionContext
    from app.models.user_model import UserModel
    context=SessionContext(); context.permissions={"cloud.view"}; context.current_user=UserModel(1,"comum",None,"Comum",None,True,False,None); menu.apply_permissions(context)
    assert not menu.provider_settings_action.isVisible()
    assert not menu.backup_action.isVisible()
    context.current_user=UserModel(2,"admin",None,"Admin",None,True,True,None); menu.apply_permissions(context)
    assert menu.provider_settings_action.isVisible()
    assert menu.backup_action.isVisible()


def test_delete_account_dialog_protects_password_and_requires_explicit_text():
    _app(); dialog=DeleteAccountDialog(); dialog.password.setText("segredo"); dialog.confirmation.setText("EXCLUIR")
    assert dialog.password.echoMode()==QLineEdit.EchoMode.Password
    assert dialog.values()==("segredo","EXCLUIR")
    dialog.close()
