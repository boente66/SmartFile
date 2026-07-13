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
    assert opened == [True]
    controller.auth_view.close()


def test_authenticated_app_keeps_existing_modules_registered(tmp_path: Path):
    app = _app(); database = Database(str(tmp_path / "smartfile.db"))
    auth = AuthController(app, database); auth.service.register_first_user(_request())
    main = MainView(); controller = AppController(main, auth.session_context, database); controller.start()
    assert {"documents", "converter", "pdf", "pdf_viewer", "scanner"} <= set(main.workspace.list_views())
    main.close()
