from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.models.document_search import DocumentSearchFilters
from app.models.registration_request import RegistrationRequest
from app.services.auth_service import AuthService
from app.services.document_request_service import DocumentRequestService
from app.services.document_service import DocumentService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_transport_service import OrganizationTransportService
from app.views.document_import_dialog import DocumentImportDialog
from app.views.document_view import DocumentView

_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _business(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    context = SessionContext()
    auth = AuthService(database, context)
    auth.register_first_user(RegistrationRequest(
        display_name="Admin", username="admin", email="admin@example.com",
        password="senha-segura", password_confirmation="senha-segura",
        template_code="BUSINESS", organization_name="Empresa",
    ))
    return database, context


def test_profiles_define_resources_independently_from_folder_templates():
    service = OrganizationFeatureService()
    personal = service.for_profile("PERSONAL")
    student = service.for_profile("STUDENT")
    business = service.for_profile("BUSINESS")

    assert personal.has("cloud_protection")
    assert student.has("indexed_filters") and student.has("digital_signature")
    assert business.has("server_transport") and business.has("document_requests")
    assert not personal.has("server_transport")


def test_schema_persists_profile_transport_requests_and_search_indexes(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    tables = {
        row["name"] for row in database.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    organization_columns = {
        row["name"] for row in database.fetch_all("PRAGMA table_info(organizations)")
    }
    indexes = {
        row["name"] for row in database.fetch_all("PRAGMA index_list(documents)")
    }
    assert {"organization_transport_settings", "document_requests"} <= tables
    assert "profile_code" in organization_columns
    assert {"idx_documents_smart_search", "idx_documents_org_category"} <= indexes


def test_schema_13_migrates_profile_without_losing_organization(tmp_path: Path):
    path = tmp_path / "legacy.db"
    database = Database(str(path))
    database.execute_query("ALTER TABLE organizations DROP COLUMN profile_code")
    database.execute_query("UPDATE organizations SET template_code='STUDENT'")
    database.execute_query("PRAGMA user_version=13")
    database.close()

    migrated = Database(str(path))
    organization = migrated.fetch_one("SELECT * FROM organizations ORDER BY id LIMIT 1")
    assert organization["name"] == "Minha Organização"
    assert organization["profile_code"] == "STUDENT"


def test_smart_search_combines_terms_and_indexed_filters(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first = tmp_path / "contrato.pdf"; first.write_bytes(b"contrato")
    second = tmp_path / "aula.txt"; second.write_bytes(b"aula")
    contract = service.import_document(
        str(first), category="Contratos", tags="cliente urgente", source_type="IMPORT",
    )
    service.import_document(
        str(second), category="Estudos", tags="faculdade", source_type="SCANNER",
    )
    service.toggle_favorite(contract.id)

    result = service.search_documents(
        "cliente urgente", filters=DocumentSearchFilters(
            file_type="PDF", source_type="IMPORT", favorite=True,
        )
    )
    assert [item.id for item in result] == [contract.id]
    assert service.search_documents(
        "cliente", filters=DocumentSearchFilters(source_type="SCANNER")
    ) == []


def test_rename_preserves_extension_and_enqueues_cloud_safely(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    source = tmp_path / "original.pdf"; source.write_bytes(b"pdf")
    document = service.import_document(str(source), sync_cloud=False)

    renamed = service.rename_document(document.id, "Contrato anual")
    assert renamed.name == "Contrato anual.pdf"
    assert Path(renamed.storage_path).is_file()
    with pytest.raises(ValueError):
        service.rename_document(document.id, "Contrato.exe")


def test_business_transport_requires_profile_and_admin_permission(tmp_path: Path):
    database, context = _business(tmp_path)
    service = OrganizationTransportService(database, context)
    organization_id = context.active_organization.id
    policy = OrganizationFeatureService(database, context)
    policy.update_enabled_features(
        context.active_organization,
        set(policy.for_organization(context.active_organization).codes) | {"server_transport"},
    )
    saved = service.configure(
        organization_id, "HTTPS", "https://ged.example.com/api",
        enabled=True, verify_tls=True,
    )
    assert saved.enabled and saved.mode == "HTTPS" and saved.verify_tls
    with pytest.raises(ValueError):
        service.configure(
            organization_id, "HTTPS", "https://user:secret@ged.example.com",
            enabled=True,
        )
    organization = context.active_organization
    organization.profile_code = "PERSONAL"
    database.execute_query(
        "UPDATE organizations SET profile_code='PERSONAL' WHERE id=?", (organization_id,)
    )
    with pytest.raises(PermissionError):
        service.configure(organization_id, "LAN", "server/share", enabled=True)


def test_business_document_requests_track_deadline_and_audit(tmp_path: Path):
    database, context = _business(tmp_path)
    service = DocumentRequestService(database, context)
    organization_id = context.active_organization.id
    policy = OrganizationFeatureService(database, context)
    policy.update_enabled_features(
        context.active_organization,
        set(policy.for_organization(context.active_organization).codes)
        | {"document_requests", "deadline_timers"},
    )
    due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    created = service.create(organization_id, "Contrato assinado", "Solicitar ao cliente", due_at=due)
    assert created.status == "OPEN"
    database.execute_query(
        "UPDATE document_requests SET due_at=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), created.id),
    )
    assert service.list_requests(organization_id)[0].status == "OVERDUE"
    service.set_status(organization_id, created.id, "COMPLETED")
    assert service.list_requests(organization_id)[0].status == "COMPLETED"
    actions = {
        row["action"] for row in database.fetch_all(
            "SELECT action FROM audit_log WHERE organization_id=?", (organization_id,)
        )
    }
    assert {"DOCUMENT_REQUEST_CREATED", "DOCUMENT_REQUEST_STATUS_CHANGED"} <= actions


def test_document_ui_exposes_left_click_context_menu_and_profile_resources(tmp_path: Path):
    _app(); database, context = _business(tmp_path)
    view = DocumentView(); view.apply_cloud_permissions(context)
    features = OrganizationFeatureService().for_profile("BUSINESS")
    view.apply_profile_features(features)
    texts = {action.text() for action in view.more_menu.actions()}
    assert {"Copiar", "Colar", "Renomear", "Mover para lixeira", "Recursos empresariais"} <= texts
    assert view.enterprise_menu.menuAction().isVisible()
    view.apply_profile_features(OrganizationFeatureService().for_profile("PERSONAL"))
    assert not view.enterprise_menu.menuAction().isVisible()
    view.close()


def test_import_dialog_returns_logical_folder_and_multiple_files(tmp_path: Path):
    _app(); database = Database(str(tmp_path / "smartfile.db"))
    service = DocumentService(db_path=database.db_name)
    folder = service.folder_service.create(service.active_organization_id, "Contratos")
    first = tmp_path / "a.pdf"; second = tmp_path / "b.pdf"
    first.write_bytes(b"a"); second.write_bytes(b"b")
    dialog = DocumentImportDialog(
        "Minha Organização", [folder], folder.id,
    )
    dialog._paths = [first.resolve(), second.resolve()]
    dialog.file_list.addItems([first.name, second.name])
    dialog.category.setText("Contratos")
    values = dialog.values()
    assert values["folder_id"] == folder.id
    assert values["paths"] == (first.resolve(), second.resolve())
    assert values["category"] == "Contratos"
    dialog.close()
