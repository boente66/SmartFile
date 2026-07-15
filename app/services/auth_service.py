from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.auth.password_service import PasswordService
from app.auth.session_context import SessionContext
from app.auth.session_service import SessionService
from app.database.database import Database
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.user_entity import UserEntity
from app.errors.auth_exceptions import (
    AccountDeletionError, EmailAlreadyExistsError, InvalidCredentialsError, PasswordPolicyError,
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
from app.services.avatar_service import AvatarService
from app.services.audit_service import AuditService

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
        self.avatars = AvatarService(database)
        self.audit = AuditService(database)

    def has_users(self) -> bool:
        return self.users.count_active() > 0

    def register_first_user(self, request: RegistrationRequest) -> UserModel:
        if self.has_users():
            if self.users.find_by_username(request.username.strip()):
                raise UserAlreadyExistsError("Nome de usuário já cadastrado.")
            if request.email and self.users.find_by_email(request.email.strip().lower()):
                raise EmailAlreadyExistsError("E-mail já cadastrado.")
            raise RegistrationError("O cadastro inicial já foi concluído.")
        return self._register_user(request, use_existing_default=True, is_superuser=True)

    def register_user(self, request: RegistrationRequest) -> UserModel:
        """Cria uma conta local com organização e armazenamento lógico isolados."""
        if not self.has_users():
            return self.register_first_user(request)
        return self._register_user(request, use_existing_default=False, is_superuser=False)

    def _register_user(
        self,
        request: RegistrationRequest,
        *,
        use_existing_default: bool,
        is_superuser: bool,
    ) -> UserModel:
        username, email, display_name = self._validate_registration(request)
        now = self._now()
        stored_avatar = None
        try:
            with self.database.transaction():
                stored_avatar = self.avatars.store(request.avatar_path)
                user = self.users.create(UserEntity(
                    username=username, email=email, display_name=display_name,
                    phone=request.phone.strip() if request.phone else None,
                    password_hash=self.passwords.hash_password(request.password),
                    is_superuser=is_superuser,
                    avatar_path=stored_avatar,
                    avatar_initials=self.avatars.initials(display_name), avatar_color="#2563eb",
                    created_at=now, updated_at=now,
                ))
                organization = (
                    self.organizations.repository.find_default()
                    if use_existing_default
                    else None
                )
                if organization is None:
                    organization = self.organizations.create(
                        request.organization_name, request.organization_description,
                        request.template_code, getattr(request, "storage_plan_code", None),
                    )
                    if use_existing_default:
                        organization.is_default = True
                        self.organizations.repository.update(organization)
                else:
                    organization=self.organizations.update(organization.id,request.organization_name,request.organization_description)
                    from app.services.storage_quota_service import PLAN_BY_TEMPLATE, StorageQuotaService
                    StorageQuotaService(self.database).assign_plan(
                        organization.id,
                        getattr(request, "storage_plan_code", None) or PLAN_BY_TEMPLATE[request.template_code.upper()],
                        request.template_code,
                    )
                organization.icon=request.organization_icon; organization.color=request.organization_color
                self.organizations.repository.update(organization)
                membership = self.members.create(OrganizationMemberEntity(
                    organization_id=organization.id, user_id=user.id, role="OWNER",
                    created_at=now, updated_at=now, joined_at=now,
                ))
                self.templates.create_template_folders(organization.id, request.template_code)
                session = self.sessions.create(user.id)
                self.audit.record("INITIAL_REGISTRATION" if use_existing_default else "LOCAL_REGISTRATION",user_id=user.id,organization_id=organization.id,target_type="organization",target_id=organization.id,description=f"Cadastro concluído com template {request.template_code}")
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
            if stored_avatar:
                from pathlib import Path
                Path(stored_avatar).unlink(missing_ok=True)
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
            self.audit.record("SESSION_REVOKED",user_id=self.session_context.current_user.id,organization_id=getattr(self.session_context.active_organization,"id",None),target_type="session",target_id=self.session_context.session_id,description="Logout realizado")
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

    def delete_current_account(self, current_password: str, confirmation: str) -> None:
        """Desativa e anonimiza a conta local sem apagar documentos ou auditoria."""
        if not self.session_context.is_authenticated():
            raise AccountDeletionError("Sessão não autenticada.")
        if confirmation.strip().upper() != "EXCLUIR":
            raise AccountDeletionError("Digite EXCLUIR para confirmar a remoção da conta.")
        user = self.users.find_by_id(self.session_context.current_user.id)
        if user is None or not self.passwords.verify_password(current_password, user.password_hash):
            raise AccountDeletionError("Senha atual inválida.")

        memberships = self.members.find_by_user(user.id)
        blocked = []
        for membership in memberships:
            if (
                membership.role == "OWNER"
                and self.members.count_active_owners(membership.organization_id) <= 1
                and self.members.count_active(membership.organization_id) > 1
            ):
                organization = self.organizations.repository.find_by_id(membership.organization_id)
                blocked.append(organization.name if organization else str(membership.organization_id))
        if blocked:
            names = ", ".join(blocked)
            raise AccountDeletionError(
                "Transfira a propriedade antes de excluir a conta. "
                f"Organizações pendentes: {names}."
            )

        now = self._now()
        previous_avatar = user.avatar_path
        token_refs: list[str] = []
        cache_providers: set[str] = set()
        with self.database.transaction() as connection:
            self.audit.record(
                "ACCOUNT_DELETED", user_id=user.id,
                organization_id=getattr(self.session_context.active_organization, "id", None),
                target_type="user", target_id=user.id,
                description="Conta local excluída e dados de identificação anonimizados",
            )
            for membership in memberships:
                if self.members.count_active(membership.organization_id) == 1:
                    setting = connection.execute(
                        "SELECT cloud_account_id FROM cloud_settings WHERE organization_id=?",
                        (membership.organization_id,),
                    ).fetchone()
                    account_id = setting["cloud_account_id"] if setting else None
                    connection.execute(
                        """UPDATE cloud_settings SET cloud_account_id=NULL,sync_mode='LOCAL',
                           paused=0,delta_token=NULL WHERE organization_id=?""",
                        (membership.organization_id,),
                    )
                    if account_id:
                        linked = connection.execute(
                            "SELECT COUNT(*) total FROM cloud_settings WHERE cloud_account_id=?",
                            (account_id,),
                        ).fetchone()["total"]
                        if linked == 0:
                            account = connection.execute(
                                "SELECT provider,token_ref FROM cloud_accounts WHERE id=?",
                                (account_id,),
                            ).fetchone()
                            if account:
                                if account["token_ref"]:
                                    token_refs.append(account["token_ref"])
                                cache_providers.add(account["provider"])
                                connection.execute("DELETE FROM cloud_accounts WHERE id=?", (account_id,))
                membership.status = "REMOVED"
                membership.deactivated_at = membership.updated_at = now
                self.members.update(membership)

            connection.execute(
                "UPDATE sessions SET revoked_at=COALESCE(revoked_at,?) WHERE user_id=?",
                (now, user.id),
            )
            user.username = f"deleted_{user.id}_{secrets.token_hex(4)}"
            user.email = None
            user.display_name = "Conta excluída"
            user.phone = None
            user.password_hash = self.passwords.hash_password(secrets.token_urlsafe(48))
            user.is_active = False
            user.is_superuser = False
            user.failed_login_attempts = 0
            user.locked_until = None
            user.avatar_path = None
            user.avatar_initials = None
            user.must_change_password = False
            user.updated_at = now
            self.users.update(user)

        from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
        try:
            config = CloudOAuthConfigService(self.database)
            for reference in token_refs:
                config.token_store.delete(reference)
            for provider in cache_providers:
                remaining = self.database.fetch_one(
                    "SELECT COUNT(*) total FROM cloud_accounts WHERE provider=?", (provider,)
                )["total"]
                if remaining == 0:
                    config.delete_cache(provider)
            if previous_avatar:
                avatar = Path(previous_avatar).resolve()
                if avatar.parent == self.avatars.directory.resolve():
                    avatar.unlink(missing_ok=True)
        except Exception:
            logger.exception("Falha na limpeza complementar da conta excluída user_id=%s", user.id)
        finally:
            logger.info("Conta local excluída user_id=%s", user.id)
            self.session_context.logout()

    def _validate_registration(self, request):
        username=request.username.strip(); display_name=" ".join(request.display_name.split()); email=request.email.strip().lower() if request.email else None
        if not display_name: raise RegistrationError("Informe o nome completo.")
        if not username or not USERNAME_PATTERN.fullmatch(username): raise RegistrationError("Username deve conter apenas letras, números, ponto, hífen ou sublinhado.")
        if self.users.find_by_username(username): raise UserAlreadyExistsError("Nome de usuário já cadastrado.")
        if email and self.users.find_by_email(email): raise EmailAlreadyExistsError("E-mail já cadastrado.")
        self._validate_password(username,request.password,request.password_confirmation)
        if request.template_code.upper() not in self.templates.TEMPLATES: raise RegistrationError("Selecione um perfil inicial.")
        if not request.organization_name.strip(): raise RegistrationError("Informe o nome da organização.")
        if len(request.organization_name.strip()) > 100: raise RegistrationError("O nome da organização deve possuir até 100 caracteres.")
        return username,email,display_name

    @staticmethod
    def _validate_password(username,password,confirmation):
        if password != confirmation: raise PasswordPolicyError("As senhas não coincidem.")
        if len(password) < 8: raise PasswordPolicyError("A senha deve possuir pelo menos 8 caracteres.")
        if password.casefold() == username.casefold(): raise PasswordPolicyError("A senha não pode ser igual ao username.")

    @staticmethod
    def _now(): return datetime.now(timezone.utc).isoformat()
