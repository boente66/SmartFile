import logging

from PyQt6.QtWidgets import QApplication

from app.auth.session_context import SessionContext
from app.controllers.account_controller import AccountController
from app.controllers.app_controller import AppController
from app.database.database import Database
from app.errors.auth_exceptions import AuthenticationError, InvalidCredentialsError
from app.services.auth_service import AuthService
from app.views.first_user_setup_view import FirstUserSetupView
from app.views.login_view import LoginView
from app.views.main_view import MainView


class AuthController:
    def __init__(self,app:QApplication,database:Database,allow_local_registration:bool=True):
        self.app=app; self.database=database; self.session_context=SessionContext(); self.service=AuthService(database,self.session_context)
        self.allow_local_registration=allow_local_registration
        self.auth_view=None; self.main_view=None; self.app_controller=None; self.account_controller=None

    def start(self):
        if self.service.has_users(): self._show_login()
        else: self._show_setup()

    def _show_login(self):
        view=LoginView(self.allow_local_registration); view.login_requested.connect(self._login)
        if self.allow_local_registration:
            view.create_account_requested.connect(self._show_registration)
        self._replace_auth_view(view)

    def _show_setup(self):
        view=FirstUserSetupView(first_user=True); view.registration_requested.connect(self._register_first_user); view.enter_requested.connect(self._open_application); self._replace_auth_view(view)

    def _show_registration(self):
        if not self.allow_local_registration:
            return
        view=FirstUserSetupView(first_user=False)
        view.registration_requested.connect(self._register_user)
        view.back_requested.connect(self._show_login)
        view.enter_requested.connect(self._open_application)
        self._replace_auth_view(view)

    def _replace_auth_view(self,view):
        if self.auth_view: self.auth_view.close()
        self.auth_view=view; view.show()

    def _login(self,login,password,remember):
        try:
            self.service.login(login,password,remember); self._open_application()
        except InvalidCredentialsError:
            self.auth_view.show_error("Usuário ou senha inválidos.")
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada durante o login")
            self.auth_view.show_error("Não foi possível entrar. Tente novamente.")

    def _register_first_user(self,request):
        try:
            self.service.register_first_user(request); self.auth_view.show_completion()
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada no cadastro inicial")
            self.auth_view.show_error("Não foi possível criar a conta. Tente novamente.")

    # Mantém o contrato que já era utilizado pelos testes e integrações locais.
    _register = _register_first_user

    def _register_user(self,request):
        try:
            self.service.register_user(request); self.auth_view.show_completion()
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada no cadastro local")
            self.auth_view.show_error("Não foi possível criar a conta. Tente novamente.")

    def _open_application(self):
        if not self.session_context.is_authenticated(): raise RuntimeError("MainView exige sessão autenticada.")
        self.auth_view.hide(); self.main_view=MainView(); self.app_controller=AppController(self.main_view,self.session_context,self.database); self.app_controller.start()
        self.account_controller=AccountController(self.main_view,self.service,self.app_controller,self.logout); self.main_view.show()

    def logout(self):
        self.service.logout()
        if self.main_view: self.main_view.close(); self.main_view=None
        self.app_controller=None; self.account_controller=None
        if self.service.has_users(): self._show_login()
        else: self._show_setup()
