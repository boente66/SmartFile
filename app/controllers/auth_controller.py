import logging

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app.auth.session_context import SessionContext
from app.controllers.account_controller import AccountController
from app.controllers.app_controller import AppController
from app.database.database import Database
from app.errors.auth_exceptions import AuthenticationError, InvalidCredentialsError
from app.services.auth_service import AuthService
from app.views.first_user_setup_view import FirstUserSetupView
from app.views.login_view import LoginView
from app.views.main_view import MainView
from app.views.password_recovery_dialog import PasswordRecoveryDialog
from app.views.recovery_codes_dialog import RecoveryCodesDialog


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
        view.recovery_requested.connect(self._recover_password)
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
            self.service.login(login,password,remember)
            codes = self._ensure_recovery_codes()
            if codes:
                RecoveryCodesDialog(codes, self.auth_view).exec()
            self._open_application()
        except InvalidCredentialsError:
            self.auth_view.show_error("Usuário ou senha inválidos.")
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada durante o login")
            self.auth_view.show_error("Não foi possível entrar. Tente novamente.")

    def _register_first_user(self,request):
        try:
            self.service.register_first_user(request)
            self.auth_view.show_completion(self._ensure_recovery_codes())
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada no cadastro inicial")
            self.auth_view.show_error("Não foi possível criar a conta. Tente novamente.")

    # Mantém o contrato que já era utilizado pelos testes e integrações locais.
    _register = _register_first_user

    def _register_user(self,request):
        try:
            self.service.register_user(request)
            self.auth_view.show_completion(self._ensure_recovery_codes())
        except AuthenticationError as exc:
            self.auth_view.show_error(str(exc))
        except Exception:
            logging.getLogger(__name__).exception("Falha inesperada no cadastro local")
            self.auth_view.show_error("Não foi possível criar a conta. Tente novamente.")

    def _recover_password(self):
        suggested = (
            self.auth_view.login_edit.text()
            if isinstance(self.auth_view, LoginView)
            else ""
        )
        dialog = PasswordRecoveryDialog(suggested, self.auth_view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.service.reset_password_with_recovery_code(*dialog.values())
            QMessageBox.information(
                self.auth_view,
                "Recuperação de senha",
                "Senha redefinida com sucesso. Entre usando a nova senha.",
            )
            self.auth_view.login_edit.setText(dialog.login.text().strip())
            self.auth_view.password_edit.setFocus()
        except AuthenticationError as exc:
            QMessageBox.warning(
                self.auth_view, "Recuperação de senha", str(exc)
            )
        except Exception:
            logging.getLogger(__name__).exception(
                "Falha inesperada na recuperação de senha"
            )
            QMessageBox.warning(
                self.auth_view,
                "Recuperação de senha",
                "Não foi possível redefinir a senha. Tente novamente.",
            )

    def _ensure_recovery_codes(self) -> tuple[str, ...]:
        """A indisponibilidade dos códigos não deve bloquear login ou cadastro."""
        try:
            return self.service.ensure_recovery_codes()
        except Exception:
            logging.getLogger(__name__).exception(
                "Não foi possível preparar códigos de recuperação"
            )
            return ()

    def _open_application(self):
        if not self.session_context.is_authenticated(): raise RuntimeError("MainView exige sessão autenticada.")
        self.auth_view.hide(); self.main_view=MainView(); self.app_controller=AppController(self.main_view,self.session_context,self.database); self.app_controller.start()
        self.account_controller=AccountController(self.main_view,self.service,self.app_controller,self.logout); self.main_view.show()
        user = self.session_context.current_user
        organization = self.session_context.active_organization
        view = self.main_view
        QTimer.singleShot(
            180,
            lambda: self._show_welcome_notification(
                view, user.display_name, getattr(organization, "name", None),
            ),
        )

    def _show_welcome_notification(
        self, view: MainView, display_name: str, organization_name: str | None,
    ) -> None:
        if view is self.main_view and view.isVisible():
            view.show_welcome_notification(display_name, organization_name)

    def logout(self):
        if self.app_controller:
            self.app_controller.shutdown()
        self.service.logout()
        if self.main_view: self.main_view.close(); self.main_view=None
        self.app_controller=None; self.account_controller=None
        if self.service.has_users(): self._show_login()
        else: self._show_setup()
