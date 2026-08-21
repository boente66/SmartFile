from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.entities.folder_entity import FolderEntity
from app.models.document_model import DocumentModel
from app.views.delivery_document_picker_dialog import DeliveryDocumentPickerDialog


_APPLICATION = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _dialog() -> DeliveryDocumentPickerDialog:
    _app()
    folders = [
        FolderEntity(id=10, organization_id=1, name="Contratos"),
        FolderEntity(id=11, organization_id=1, parent_id=10, name="2026"),
        FolderEntity(id=12, organization_id=1, parent_id=11, name="Vazia"),
    ]
    documents = [
        DocumentModel(
            id=1, organization_id=1, folder_id=10, name="Contrato A.pdf",
            path="/storage/interno/uuid-secreto.pdf", file_type="PDF",
            extension=".pdf", size=1280, created_at="2026-08-20T10:00:00",
        ),
        DocumentModel(
            id=2, organization_id=1, folder_id=11, name="Contrato B.pdf",
            path="/storage/interno/outro-uuid.pdf", file_type="PDF",
            extension=".pdf", size=2048, created_at="2026-08-20T11:00:00",
        ),
    ]
    return DeliveryDocumentPickerDialog(
        documents, folders, organization_name="Minha Organização",
    )


def _select_document(dialog: DeliveryDocumentPickerDialog, document_id: int) -> None:
    for row in range(dialog.table.rowCount()):
        item = dialog.table.item(row, 0)
        if item.data(dialog.KIND_ROLE) == "document" and item.data(dialog.ID_ROLE) == document_id:
            for column in range(dialog.table.columnCount()):
                dialog.table.item(row, column).setSelected(True)
            return
    raise AssertionError(f"documento {document_id} não está na pasta atual")


def test_picker_navigates_logical_folders_and_back_without_exposing_storage() -> None:
    dialog = _dialog()
    assert not dialog.back_button.isEnabled()
    assert dialog.breadcrumb.text() == "Minha Organização"

    dialog._show_folder(10)
    assert dialog.back_button.isEnabled()
    assert dialog.breadcrumb.text() == "Minha Organização  ›  Contratos"
    visible = " ".join(
        dialog.table.item(row, column).text()
        for row in range(dialog.table.rowCount())
        for column in range(dialog.table.columnCount())
    )
    assert "Contrato A.pdf" in visible
    assert "/storage/" not in visible

    dialog._show_folder(11)
    dialog.go_back()
    assert dialog._current_folder_id == 10
    dialog.go_back()
    assert dialog._current_folder_id is None
    assert not dialog.back_button.isEnabled()


def test_picker_keeps_multiselection_between_folders_and_only_returns_documents() -> None:
    dialog = _dialog()
    assert not dialog.add_button.isEnabled()

    dialog._show_folder(10)
    _select_document(dialog, 1)
    dialog._selection_changed()
    dialog._show_folder(11)
    _select_document(dialog, 2)
    dialog._selection_changed()

    assert dialog.selected_document_ids() == [1, 2]
    assert dialog.add_button.isEnabled()
    assert "2 documento(s)" in dialog.selection_status.text()

    dialog._show_folder(10)
    selected_rows = {item.row() for item in dialog.table.selectedItems()}
    assert selected_rows


def test_picker_search_and_empty_folder_have_clear_states() -> None:
    dialog = _dialog()
    dialog._show_folder(11)
    dialog.search.setText("inexistente")
    assert not dialog.empty_state.isHidden()
    assert "Nenhum item" in dialog.empty_state.text()

    dialog._show_folder(12)
    assert dialog.table.rowCount() == 0
    assert not dialog.empty_state.isHidden()
    assert "vazia" in dialog.empty_state.text()
