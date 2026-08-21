from __future__ import annotations

import os
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.user_entity import UserEntity
from app.models.registration_request import RegistrationRequest
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.document_request_service import DocumentRequestService
from app.controllers.document_request_controller import DocumentRequestController
from app.services.organization_admin_service import OrganizationAdminService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_transport_service import OrganizationTransportService
from app.services.version_notification_service import VersionNotificationService

_APPLICATION = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _business(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    context = SessionContext()
    AuthService(database, context).register_first_user(RegistrationRequest(
        display_name="Admin", username="admin", email="admin@example.com",
        password="senha-segura", password_confirmation="senha-segura",
        template_code="BUSINESS", organization_name="Empresa",
    ))
    return database, context


def _enable(database, context, *codes: str):
    policy = OrganizationFeatureService(database, context)
    current = set(policy.for_organization(context.active_organization).codes)
    return policy.update_enabled_features(context.active_organization, current | set(codes))


def _user(database: Database, username: str, *, active: bool = True) -> UserEntity:
    now = datetime.now(timezone.utc).isoformat()
    return UserRepository(database=database).create(UserEntity(
        username=username, display_name=username.title(), password_hash="test-only",
        is_active=active, created_at=now, updated_at=now,
    ))


def _member(database: Database, organization_id: int, user_id: int, status="ACTIVE"):
    now = datetime.now(timezone.utc).isoformat()
    return OrganizationMemberRepository(database=database).create(
        OrganizationMemberEntity(
            organization_id=organization_id, user_id=user_id, role="EDITOR",
            status=status, created_at=now, updated_at=now,
        )
    )


def test_business_defaults_are_conservative_and_features_are_independent(tmp_path: Path):
    database, context = _business(tmp_path)
    policy = OrganizationFeatureService(database, context)
    enabled = policy.for_organization(context.active_organization)

    assert enabled.has("access_control") and enabled.has("audit_history")
    assert not enabled.has("server_transport")
    assert not enabled.has("document_requests")
    assert not enabled.has("deadline_timers")
    assert not enabled.has("cloud_sync")

    policy.update_enabled_features(
        context.active_organization, set(enabled.codes) | {"server_transport"},
    )
    transport_only = policy.for_organization(context.active_organization)
    assert transport_only.has("server_transport")
    assert not transport_only.has("document_requests")

    policy.update_enabled_features(
        context.active_organization,
        (set(transport_only.codes) - {"server_transport"}) | {"document_requests"},
    )
    requests_only = policy.for_organization(context.active_organization)
    assert requests_only.has("document_requests")
    assert not requests_only.has("server_transport")


def test_transport_does_not_require_cloud_account_or_cloud_mode(tmp_path: Path):
    database, context = _business(tmp_path)
    _enable(database, context, "server_transport")
    organization_id = context.active_organization.id
    cloud = database.fetch_one(
        "SELECT * FROM cloud_settings WHERE organization_id=?", (organization_id,)
    )
    assert cloud["cloud_account_id"] is None and cloud["sync_mode"] == "LOCAL"

    service = OrganizationTransportService(database, context)
    nas = service.configure(
        organization_id, "NAS", r"\\servidor\documentos", enabled=True,
    )
    https = service.configure(
        organization_id, "HTTPS", "https://ged.example.com/api",
        enabled=True, verify_tls=True,
    )
    assert nas.mode == "NAS" and https.mode == "HTTPS" and https.verify_tls


@pytest.mark.parametrize("profile", ["PERSONAL", "STUDENT", "EMPTY"])
def test_non_business_profile_cannot_enable_transport_even_if_setting_is_injected(
    tmp_path: Path, profile: str,
):
    database, context = _business(tmp_path)
    organization_id = context.active_organization.id
    database.execute_query(
        "UPDATE organizations SET profile_code=? WHERE id=?", (profile, organization_id)
    )
    context.active_organization.profile_code = profile
    database.execute_query(
        """
        INSERT OR REPLACE INTO organization_feature_settings
        (organization_id,feature_code,enabled,updated_at) VALUES (?,?,1,?)
        """,
        (organization_id, "server_transport", datetime.now(timezone.utc).isoformat()),
    )
    with pytest.raises(PermissionError):
        OrganizationTransportService(database, context).configure(
            organization_id, "LAN", "fileserver/documentos", enabled=True,
        )


def test_transport_endpoint_validation_and_permission(tmp_path: Path):
    database, context = _business(tmp_path)
    _enable(database, context, "server_transport")
    service = OrganizationTransportService(database, context)
    organization_id = context.active_organization.id

    for mode, endpoint in (
        ("HTTPS", "http://ged.example.com"),
        ("HTTPS", "https:///sem-host"),
        ("HTTPS", "https://user:password@ged.example.com"),
        ("NAS", "pasta/relativa"),
        ("LAN", "fileserver/../segredo"),
    ):
        with pytest.raises(ValueError):
            service.configure(organization_id, mode, endpoint, enabled=True)

    context.memberships[0].role = "VIEWER"
    context.current_user = replace(context.current_user, is_superuser=False)
    context.set_active_organization(context.active_organization)
    with pytest.raises(Exception, match="Permissão insuficiente"):
        service.configure(organization_id, "LAN", "fileserver/documentos", enabled=True)


def test_document_request_assignee_must_be_active_member_of_same_organization(tmp_path: Path):
    database, context = _business(tmp_path)
    _enable(database, context, "document_requests")
    organization_id = context.active_organization.id
    valid = _user(database, "valid")
    inactive_user = _user(database, "inactive-user", active=False)
    inactive_member = _user(database, "inactive-member")
    outsider = _user(database, "outsider")
    _member(database, organization_id, valid.id)
    _member(database, organization_id, inactive_user.id)
    _member(database, organization_id, inactive_member.id, status="INACTIVE")

    service = DocumentRequestService(database, context)
    assert service.create(organization_id, "Sem responsável").assigned_to_user_id is None
    assert service.create(
        organization_id, "Contrato", assigned_to_user_id=valid.id,
    ).assigned_to_user_id == valid.id
    for user_id in (inactive_user.id, inactive_member.id, outsider.id, 999999):
        with pytest.raises(ValueError):
            service.create(organization_id, "Documento", assigned_to_user_id=user_id)


def test_viewer_can_view_requests_but_cannot_create_or_update(tmp_path: Path):
    _app()
    database, context = _business(tmp_path)
    _enable(database, context, "document_requests")
    context.memberships[0].role = "VIEWER"
    context.current_user = replace(context.current_user, is_superuser=False)
    context.set_active_organization(context.active_organization)
    controller = DocumentRequestController(
        database, context,
        organization_id_provider=lambda: context.active_organization.id,
    )
    dialog = controller.open_requests(modal=False)
    assert not dialog.create_button.isEnabled()
    assert not dialog.update_button.isEnabled()
    dialog.close()


def test_profile_update_is_transactional_validated_and_audited(tmp_path: Path):
    database, context = _business(tmp_path)
    service = OrganizationAdminService(database, context)
    organization = context.active_organization
    updated = service.update(
        organization.id, "Empresa Atualizada", profile_code="PERSONAL",
    )
    context.set_active_organization(updated)
    assert updated.profile_code == "PERSONAL"
    assert database.fetch_one(
        "SELECT profile_code FROM organizations WHERE id=?", (organization.id,)
    )["profile_code"] == "PERSONAL"
    assert database.fetch_one(
        """
        SELECT 1 FROM audit_log WHERE organization_id=?
        AND action='ORGANIZATION_PROFILE_UPDATED'
        """,
        (organization.id,),
    )

    with pytest.raises(ValueError, match="Perfil de recursos inválido"):
        service.update(organization.id, "Não deve persistir", profile_code="INVALID")
    assert database.fetch_one(
        "SELECT name FROM organizations WHERE id=?", (organization.id,)
    )["name"] == "Empresa Atualizada"


def test_schema_14_upgrade_preserves_transport_and_adds_feature_policy(tmp_path: Path):
    path = tmp_path / "schema14.db"
    database, context = _business(tmp_path)
    source = Path(database.db_name)
    database.close()
    path.write_bytes(source.read_bytes())
    legacy = Database(str(path))
    legacy.execute_query("DROP TABLE organization_feature_settings")
    legacy.execute_query(
        "ALTER TABLE organization_transport_settings DROP COLUMN credential_ref"
    )
    legacy.execute_query("PRAGMA user_version=14")
    legacy.close()

    migrated = Database(str(path))
    assert migrated.connect().execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    tables = {
        row["name"] for row in migrated.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    columns = {
        row["name"] for row in migrated.fetch_all(
            "PRAGMA table_info(organization_transport_settings)"
        )
    }
    assert "organization_feature_settings" in tables
    assert "credential_ref" in columns


def test_version_notification_is_shown_once_per_version(tmp_path: Path):
    database = Database(str(tmp_path / "version.db"))
    service = VersionNotificationService(database)
    assert service.should_notify()
    from app.version import __version__
    service.acknowledge(__version__)
    assert not service.should_notify()


def test_version_notification_revision_alerts_existing_beta_installation(tmp_path: Path):
    database = Database(str(tmp_path / "version-revision.db"))
    from app.version import __version__
    database.execute_query(
        "INSERT INTO app_settings(key,value) VALUES(?,?)",
        (VersionNotificationService.SETTING_KEY, f"{__version__}:corporate-nas-1"),
    )
    service = VersionNotificationService(database)
    assert service.should_notify()
    assert "descoberta automática" in service.message()
    service.acknowledge(__version__)
    assert not service.should_notify()
