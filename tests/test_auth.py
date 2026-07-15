from pathlib import Path
from dataclasses import replace

import pytest

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.errors.auth_exceptions import (
    AccountDeletionError, EmailAlreadyExistsError, InvalidCredentialsError, PasswordPolicyError,
    RegistrationError, UserAlreadyExistsError, UserInactiveError,
)
from app.models.registration_request import RegistrationRequest
from app.entities.organization_entity import OrganizationEntity
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.services.auth_service import AuthService


def _request(template="PERSONAL", username="pessoa", email="pessoa@example.com"):
    return RegistrationRequest(
        display_name="Pessoa Teste", username=username, email=email, phone=None,
        password="senha-segura", password_confirmation="senha-segura",
        template_code=template,
    )


def test_first_access_registration_hash_membership_session_and_logout(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); context = SessionContext()
    auth = AuthService(database, context)
    assert auth.has_users() is False

    user = auth.register_first_user(_request())

    stored = database.fetch_one("SELECT * FROM users WHERE id=?", (user.id,))
    member = database.fetch_one("SELECT * FROM organization_members WHERE user_id=?", (user.id,))
    session = database.fetch_one("SELECT * FROM sessions WHERE user_id=?", (user.id,))
    assert stored["password_hash"].startswith("$argon2id$")
    assert stored["is_superuser"] == 1
    assert "senha-segura" not in stored["password_hash"]
    assert member["role"] == "OWNER"
    assert session["token_hash"] and "senha" not in session["token_hash"]
    assert context.is_authenticated() and context.has_permission("document.import")

    session_id = context.session_id; auth.logout()
    assert context.is_authenticated() is False
    assert database.fetch_one("SELECT revoked_at FROM sessions WHERE id=?", (session_id,))["revoked_at"]


@pytest.mark.parametrize(
    ("template", "expected"),
    [("PERSONAL", 6), ("STUDENT", 6), ("BUSINESS", 8), ("EMPTY", 0)],
)
def test_initial_folder_templates_are_logical_and_persistent(tmp_path: Path, template, expected):
    database = Database(str(tmp_path / f"{template}.db")); auth = AuthService(database)
    auth.register_first_user(_request(template=template))
    organization_id = auth.session_context.active_organization.id
    folders = database.fetch_all("SELECT * FROM folders WHERE organization_id=? AND status='ACTIVE'", (organization_id,))
    assert len(folders) == expected
    assert not any((database.storage_dir / row["name"]).exists() for row in folders)
    reopened = Database(str(tmp_path / f"{template}.db"))
    assert len(reopened.fetch_all("SELECT * FROM folders WHERE organization_id=? AND status='ACTIVE'", (organization_id,))) == expected


def test_login_wrong_password_inactive_and_change_password(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); first = AuthService(database)
    user = first.register_first_user(_request()); first.logout()
    auth = AuthService(database, SessionContext())
    with pytest.raises(InvalidCredentialsError): auth.login("pessoa", "incorreta")
    logged = auth.login("PESSOA@EXAMPLE.COM", "senha-segura")
    assert logged.id == user.id and auth.session_context.is_authenticated()
    auth.change_password("senha-segura", "nova-senha-123", "nova-senha-123"); auth.logout()
    assert auth.login("pessoa", "nova-senha-123").id == user.id
    entity = auth.users.find_by_id(user.id); entity.is_active=False; auth.users.update(entity); auth.logout()
    with pytest.raises(UserInactiveError): auth.login("pessoa", "nova-senha-123")


def test_password_policy_and_duplicate_registration_are_rejected(tmp_path: Path):
    auth = AuthService(Database(str(tmp_path / "smartfile.db")))
    weak = replace(_request(), password="curta", password_confirmation="curta")
    with pytest.raises(PasswordPolicyError): auth.register_first_user(weak)
    auth.register_first_user(_request())
    with pytest.raises(UserAlreadyExistsError): auth.register_first_user(_request())
    with pytest.raises(EmailAlreadyExistsError):
        auth.register_first_user(_request(username="outra", email="pessoa@example.com"))


def test_registration_rolls_back_everything_when_template_fails(tmp_path: Path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    monkeypatch.setattr(auth.templates, "create_template_folders", lambda *_args: (_ for _ in ()).throw(RuntimeError("falha")))
    with pytest.raises(RegistrationError): auth.register_first_user(_request())
    assert database.fetch_one("SELECT COUNT(*) total FROM users")["total"] == 0
    assert database.fetch_one("SELECT COUNT(*) total FROM sessions")["total"] == 0
    assert database.fetch_one("SELECT COUNT(*) total FROM organization_members")["total"] == 0


def test_additional_local_user_gets_isolated_organization_and_template(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    first = auth.register_first_user(_request())
    first_organization = auth.session_context.active_organization.id
    auth.logout()

    second = auth.register_user(
        _request(template="STUDENT", username="estudante", email="estudante@example.com")
    )
    second_organization = auth.session_context.active_organization.id

    assert second.id != first.id and second.is_superuser is False
    assert second_organization != first_organization
    membership = auth.members.find(second_organization, second.id)
    assert membership is not None and membership.role == "OWNER"
    folders = database.fetch_all(
        "SELECT name FROM folders WHERE organization_id=? AND status='ACTIVE' ORDER BY name",
        (second_organization,),
    )
    assert {row["name"] for row in folders} == set(auth.templates.TEMPLATES["STUDENT"])
    assert auth.members.find(first_organization, second.id) is None


def test_additional_registration_rolls_back_all_records(tmp_path: Path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    auth.register_first_user(_request()); auth.logout()
    before_organizations = database.fetch_one("SELECT COUNT(*) total FROM organizations")["total"]
    monkeypatch.setattr(
        auth.templates,
        "create_template_folders",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("falha")),
    )

    with pytest.raises(RegistrationError):
        auth.register_user(_request(username="outra", email="outra@example.com"))

    assert auth.users.find_by_username("outra") is None
    assert database.fetch_one("SELECT COUNT(*) total FROM organizations")["total"] == before_organizations


def test_auth_migration_is_idempotent(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); Database(str(tmp_path / "smartfile.db"))
    tables = {row["name"] for row in database.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "sessions", "organization_members"} <= tables
    assert database.connect().execute("PRAGMA user_version").fetchone()[0] == 11


def test_migration_promotes_first_active_user_to_system_administrator(tmp_path: Path):
    path = tmp_path / "smartfile.db"; database = Database(str(path)); auth = AuthService(database)
    user = auth.register_first_user(_request())
    database.execute_query("UPDATE users SET is_superuser=0 WHERE id=?", (user.id,))
    database.connect().execute("PRAGMA user_version=10"); database.close()
    reopened = Database(str(path))
    assert reopened.fetch_one("SELECT is_superuser FROM users WHERE id=?", (user.id,))["is_superuser"] == 1
    assert reopened.connect().execute("PRAGMA user_version").fetchone()[0] == 11


def test_repeated_failures_lock_account_without_revealing_credentials(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    auth.register_first_user(_request()); auth.logout()
    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            auth.login("pessoa", "senha-incorreta")
    from app.errors.auth_exceptions import UserLockedError
    with pytest.raises(UserLockedError):
        auth.login("pessoa", "senha-segura")


def test_session_context_switches_only_to_linked_organization():
    context = SessionContext()
    first = OrganizationEntity(id=1, name="Primeira")
    second = OrganizationEntity(id=2, name="Segunda")
    memberships = [
        OrganizationMemberEntity(organization_id=1, user_id=1, role="OWNER"),
        OrganizationMemberEntity(organization_id=2, user_id=1, role="EDITOR"),
    ]
    from app.models.user_model import UserModel
    user = UserModel(1, "pessoa", None, "Pessoa", None, True, False, None)
    context.login(user, 1, first, memberships)
    context.set_active_organization(second)
    assert context.active_organization.id == 2
    assert context.has_permission("document.import") is True
    with pytest.raises(Exception):
        context.set_active_organization(OrganizationEntity(id=3, name="Terceira"))


def test_delete_account_anonymizes_identity_revokes_sessions_and_allows_new_setup(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    user = auth.register_first_user(_request())
    avatar = database.data_dir / "avatars" / "fake.png"; avatar.parent.mkdir(exist_ok=True); avatar.write_bytes(b"avatar")
    entity = auth.users.find_by_id(user.id); entity.avatar_path = str(avatar); auth.users.update(entity)

    with pytest.raises(AccountDeletionError):
        auth.delete_current_account("senha-incorreta", "EXCLUIR")
    auth.delete_current_account("senha-segura", "EXCLUIR")

    deleted = auth.users.find_by_id(user.id)
    assert deleted.is_active is False and deleted.email is None
    assert deleted.username.startswith(f"deleted_{user.id}_")
    assert deleted.display_name == "Conta excluída" and deleted.avatar_path is None
    assert auth.session_context.is_authenticated() is False and auth.has_users() is False
    assert not avatar.exists()
    assert database.fetch_one(
        "SELECT COUNT(*) total FROM sessions WHERE user_id=? AND revoked_at IS NULL", (user.id,)
    )["total"] == 0
    assert database.fetch_one(
        "SELECT status FROM organization_members WHERE user_id=?", (user.id,)
    )["status"] == "REMOVED"
    replacement = auth.register_first_user(_request(username="nova", email="nova@example.com"))
    assert replacement.is_active and auth.session_context.is_authenticated()


def test_delete_account_requires_ownership_transfer_when_other_members_exist(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db")); auth = AuthService(database)
    owner = auth.register_first_user(_request())
    organization_id = auth.session_context.active_organization.id
    from app.services.member_service import MemberService
    MemberService(database, auth.session_context).create_user(
        organization_id, "Outro usuário", "outro", "senha-temporaria", role="EDITOR"
    )
    with pytest.raises(AccountDeletionError, match="Transfira a propriedade"):
        auth.delete_current_account("senha-segura", "EXCLUIR")
    assert auth.users.find_by_id(owner.id).is_active is True
