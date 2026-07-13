from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from app.auth.password_service import PasswordService
from app.auth.session_context import SessionContext
from app.auth.session_service import SessionService
from app.database.database import Database
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.user_entity import UserEntity
from app.errors.auth_exceptions import (
    EmailAlreadyExistsError, InvalidCredentialsError, PasswordPolicyError,
    RegistrationError, UserAlreadyExistsError, UserInactiveError, UserLockedError,
)
from app.models.registration_request import RegistrationRequest
from app.models.user_model import UserModel
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository
from app.services.folder_service import FolderService
from app.services.folder_template_service import FolderTemplateService
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class AuthService:
    def __init__(self, database: Database, session_context: SessionContext | None = None):
        self.database = database; self.session_context = session_context or SessionContext()
        self.users = UserRepository(database=database)
        self.members = OrganizationMemberRepository(database=database)
        self.sessions = SessionService(SessionRepository(database=database))
        self.passwords = PasswordService()
        self.organizations = OrganizationService(database)
        self.templates = FolderTemplateService(FolderService(database))

    def has_users(self) -> bool:
        return self.users.count() > 0

    def register_first_user(self, request: RegistrationRequest) -> UserModel:
        if self.has_users():
            if self.users.find_by_username(request.username.strip()):
                raise UserAlreadyExistsError("Nome de usuário já cadastrado.")
            if request.email and self.users.find_by_email(request.email.strip().lower()):
                raise EmailAlreadyExistsError("E-mail já cadastrado.")
            raise RegistrationError("O cadastro inicial já foi concluído.")
        return self._register_user(request, use_existing_default=True)

    def register_user(self, request: RegistrationRequest) -> UserModel:
        """Cria uma conta local com organização e armazenamento lógico isolados."""
        if not self.has_users():
            return self.register_first_user(request)
        return self._register_user(request, use_existing_default=False)

    def _register_user(
        self,
        request: RegistrationRequest,
        *,
        use_existing_default: bool,
    ) -> UserModel:
        username, email, display_name = self._validate_registration(request)
        now = self._now()
        try:
            with self.database.transaction():
                user = self.users.create(UserEntity(
                    username=username, email=email, display_name=display_name,
                    phone=request.phone.strip() if request.phone else None,
                    password_hash=self.passwords.hash_password(request.password),
                    created_at=now, updated_at=now,
                ))
                organization = (
                    self.organizations.repository.find_default()
                    if use_existing_default
                    else None
                )
                if organization is None:
                    organization = self.organizations.create("Minha Organização")
                    if use_existing_default:
                        organization.is_default = True
                        self.organizations.repository.update(organization)
                membership = self.members.create(OrganizationMemberEntity(
                    organization_id=organization.id, user_id=user.id, role="OWNER",
                    created_at=now, updated_at=now,
                ))
                self.templates.create_template_folders(organization.id, request.template_code)
                session = self.sessions.create(user.id)
            model = UserModel.from_entity(user)
            self.session_context.login(model, session.id, organization, [membership])
            self.organizations.set_active(organization.id)
            logger.info(
                "%s criado id=%s template=%s organization_id=%s",
                "Primeiro usuário" if use_existing_default else "Usuário local",
                user.id,
                request.template_code,
                organization.id,
            )
            return model
        except (UserAlreadyExistsError, EmailAlreadyExistsError, PasswordPolicyError):
            raise
        except Exception as exc:
            raise RegistrationError("Não foi possível concluir o cadastro inicial.") from exc

    def login(self, login: str, password: str, remember: bool = False) -> UserModel:
        normalized = login.strip().lower()
        user = self.users.find_by_login(normalized) if normalized else None
        generic = InvalidCredentialsError("Usuário ou senha inválidos.")
        if user is None:
            logger.warning("Tentativa de login inválida")
            raise generic
        if not user.is_active:
            raise UserInactiveError("Usuário inativo.")
        if user.locked_until and datetime.fromisoformat(user.locked_until) > datetime.now(timezone.utc):
            raise UserLockedError("Conta temporariamente bloqueada. Tente novamente mais tarde.")
        if not self.passwords.verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= 5:
                user.locked_until = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
                user.failed_login_attempts = 0
            user.updated_at = self._now(); self.users.update(user)
            logger.warning("Tentativa de login inválida user_id=%s", user.id)
            raise generic
        if self.passwords.needs_rehash(user.password_hash):
            user.password_hash = self.passwords.hash_password(password)
        user.failed_login_attempts = 0; user.locked_until = None
        user.last_login_at = user.updated_at = self._now(); self.users.update(user)
        memberships = self.members.find_by_user(user.id)
        if not memberships:
            raise InvalidCredentialsError("Usuário sem organização ativa.")
        organization = self.organizations.repository.find_by_id(memberships[0].organization_id)
        session = self.sessions.create(user.id, remember)
        model = UserModel.from_entity(user)
        self.session_context.login(model, session.id, organization, memberships)
        self.organizations.set_active(organization.id)
        logger.info("Login bem-sucedido user_id=%s", user.id)
        return model

    def logout(self) -> None:
        if self.session_context.session_id:
            self.sessions.revoke(self.session_context.session_id)
            logger.info("Logout user_id=%s", getattr(self.session_context.current_user, "id", None))
        self.session_context.logout()

    def change_password(self, current_password: str, new_password: str, confirmation: str) -> None:
        if not self.session_context.is_authenticated():
            raise InvalidCredentialsError("Sessão não autenticada.")
        user = self.users.find_by_id(self.session_context.current_user.id)
        if not user or not self.passwords.verify_password(current_password, user.password_hash):
            raise InvalidCredentialsError("Senha atual inválida.")
        self._validate_password(user.username, new_password, confirmation)
        user.password_hash = self.passwords.hash_password(new_password); user.updated_at = self._now()
        self.users.update(user); logger.info("Senha alterada user_id=%s", user.id)

    def _validate_registration(self, request):
        username=request.username.strip(); display_name=" ".join(request.display_name.split()); email=request.email.strip().lower() if request.email else None
        if not display_name: raise RegistrationError("Informe o nome completo.")
        if not username or not USERNAME_PATTERN.fullmatch(username): raise RegistrationError("Username deve conter apenas letras, números, ponto, hífen ou sublinhado.")
        if self.users.find_by_username(username): raise UserAlreadyExistsError("Nome de usuário já cadastrado.")
        if email and self.users.find_by_email(email): raise EmailAlreadyExistsError("E-mail já cadastrado.")
        self._validate_password(username,request.password,request.password_confirmation)
        if request.template_code.upper() not in self.templates.TEMPLATES: raise RegistrationError("Selecione um perfil inicial.")
        return username,email,display_name

    @staticmethod
    def _validate_password(username,password,confirmation):
        if password != confirmation: raise PasswordPolicyError("As senhas não coincidem.")
        if len(password) < 8: raise PasswordPolicyError("A senha deve possuir pelo menos 8 caracteres.")
        if password.casefold() == username.casefold(): raise PasswordPolicyError("A senha não pode ser igual ao username.")

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
