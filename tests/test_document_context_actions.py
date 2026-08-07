import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

from app.models.document_model import DocumentModel
from app.views.document_view import DocumentView

_APPLICATION = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _selected_view() -> DocumentView:
    app = _app()
    view = DocumentView()
    view.set_documents([DocumentModel(id=42, name="contrato.pdf", file_type="PDF")])
    view.resize(1400, 720)
    view.show()
    view.documents_table.selectRow(0)
    view.documents_table.setFocus()
    app.processEvents()
    return view


def test_left_click_on_more_button_opens_contextual_menu():
    view = _selected_view()
    shown = QSignalSpy(view.more_menu.aboutToShow)
    QTimer.singleShot(50, view.more_menu.close)

    QTest.mouseClick(view.btn_more, Qt.MouseButton.LeftButton)
    _app().processEvents()

    assert len(shown) == 1
    assert view.btn_more.menu() is view.more_menu
    view.more_menu.close()
    view.close()


def test_document_keyboard_shortcuts_emit_expected_actions():
    view = _selected_view()
    copied = QSignalSpy(view.copy_requested)
    pasted = QSignalSpy(view.paste_requested)
    renamed = QSignalSpy(view.rename_document_requested)
    trashed = QSignalSpy(view.delete_requested)

    QTest.keyClick(view.documents_table, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(view.documents_table, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(view.documents_table, Qt.Key.Key_F2)
    QTest.keyClick(view.documents_table, Qt.Key.Key_Delete)
    _app().processEvents()

    assert list(copied[0]) == [42]
    assert len(pasted) == 1
    assert list(renamed[0]) == [42]
    assert list(trashed[0]) == [42]
    view.close()


def test_keyboard_context_menu_shortcuts_and_trash_delete_are_available():
    view = _selected_view()
    permanently_deleted = QSignalSpy(view.permanent_delete_requested)

    assert view.document_shortcuts["context"].key().toString() == "Shift+F10"
    assert view.document_shortcuts["menu"].key().toString() == "Menu"

    view._select_scope("trash")
    QTest.keyClick(view.documents_table, Qt.Key.Key_Delete)
    _app().processEvents()

    assert list(permanently_deleted[0]) == [42]
    view.close()
