from __future__ import annotations

import os
import sqlite3
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.services.document_service import DocumentService
from app.views.document_view import DocumentView

_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def test_default_organization_is_created_and_crud_persists(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))
    organizations = service.organization_service.list_organizations()

    assert len(organizations) == 1
    assert organizations[0].name == "Minha Organização"
    assert organizations[0].is_default is True
    company = service.organization_service.create("Empresa Ágil", "Corporativo")
    assert company.slug == "empresa-agil"
    updated = service.organization_service.update(company.id, "Empresa ABC", "Atualizada")
    assert updated.name == "Empresa ABC"
    service.set_active_organization(company.id)

    reopened = DocumentService(db_path=str(db_path))
    assert {item.name for item in reopened.organization_service.list_organizations()} == {
        "Minha Organização", "Empresa ABC"
    }
    assert reopened.active_organization_id == company.id
    assert reopened.organization_service.delete(company.id) is True
    with pytest.raises(ValueError):
        reopened.organization_service.delete(organizations[0].id)


def test_folders_support_subfolders_rename_move_and_safe_delete(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    organization_id = service.active_organization_id
    finance = service.folder_service.create(organization_id, "Financeiro")
    year = service.folder_service.create(organization_id, "2026", finance.id)
    invoices = service.folder_service.create(organization_id, "Notas Fiscais", year.id)

    assert service.folder_service.rename(organization_id, invoices.id, "Notas").name == "Notas"
    service.folder_service.move(organization_id, invoices.id, finance.id)
    assert service.folder_service.repository.find_by_id(invoices.id).parent_id == finance.id
    with pytest.raises(ValueError):
        service.folder_service.move(organization_id, finance.id, invoices.id)

    assert service.delete_folder(finance.id) is True
    assert service.folder_service.list_folders(organization_id) == []


def test_documents_are_isolated_and_same_checksum_is_allowed_between_organizations(tmp_path: Path):
    source = tmp_path / "documento.pdf"
    source.write_bytes(b"mesmo conteudo")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    default_id = service.active_organization_id
    first = service.import_document(str(source))
    company = service.organization_service.create("Empresa ABC")

    service.set_active_organization(company.id)
    assert service.list_documents() == []
    second = service.import_document(str(source))
    assert second.organization_id == company.id
    assert first.checksum == second.checksum
    assert service.get_document(first.id) is None

    service.set_active_organization(default_id)
    assert [item.id for item in service.list_documents()] == [first.id]
    assert service.get_document(second.id) is None


def test_legacy_documents_are_migrated_to_default_organization(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, original_name TEXT,
            path TEXT NOT NULL, file_type TEXT, extension TEXT, size INTEGER,
            category TEXT, tags TEXT, favorite INTEGER, checksum TEXT,
            created_at TEXT, updated_at TEXT, last_accessed_at TEXT
        )
        """
    )
    connection.execute(
        "INSERT INTO documents (id, name, path, checksum) VALUES (1, 'legado.pdf', '/tmp/legado.pdf', 'abc')"
    )
    connection.commit(); connection.close()

    database = Database(db_name=str(db_path))
    row = database.fetch_one(
        """
        SELECT documents.organization_id, organizations.name
        FROM documents JOIN organizations ON organizations.id = documents.organization_id
        WHERE documents.id = 1
        """
    )

    assert row["name"] == "Minha Organização"
    assert row["organization_id"] is not None
    assert database.connect().execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION


def test_document_view_updates_organization_and_folder_tree():
    app = _app()
    service = DocumentService(db_path=":memory:")
    default = service.organization_service.active()
    folder = service.folder_service.create(default.id, "Contratos")
    child = service.folder_service.create(default.id, "Clientes", folder.id)
    view = DocumentView()
    view.set_organizations(service.organization_service.list_organizations(), default.id)
    view.set_folders(default.name, service.folder_service.list_folders(default.id))
    view.resize(1200, 700); view.show(); app.processEvents()

    root = view.folder_tree.topLevelItem(0)
    assert view.organization_combo.currentText() == "Minha Organização"
    assert root.text(0) == "Minha Organização"
    assert root.child(0).data(0, 256) == folder.id
    assert root.child(0).child(0).data(0, 256) == child.id
    assert all(not button.icon().isNull() for button in view.document_toolbar_buttons)
    view.close()
