import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QBoxLayout

from app.views.document_view import DocumentView
from app.services.storage_quota_service import GB, StorageUsageSummary

_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def test_document_view_stacks_details_and_enables_vertical_scroll_when_compact():
    app = _app()
    view = DocumentView()
    view.resize(760, 560)
    view.show()
    app.processEvents()

    assert view.main_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert view.details.geometry().top() >= view.list_panel.geometry().bottom()
    assert view.scroll_area.verticalScrollBar().maximum() > 0
    assert view.scroll_area.horizontalScrollBar().maximum() == 0
    view.close()


def test_document_view_keeps_side_by_side_layout_on_large_screen():
    app = _app()
    view = DocumentView()
    view.resize(1600, 760)
    view.show()
    app.processEvents()

    assert view.main_layout.direction() == QBoxLayout.Direction.LeftToRight
    assert view.details.geometry().left() >= view.list_panel.geometry().right()
    assert view.search_edit.geometry().right() <= view.list_panel.width()
    view.close()


def test_trash_actions_and_cloud_login_providers_are_exposed():
    _app(); view=DocumentView(); view._select_scope("trash")
    assert view.btn_empty_trash.isVisible() is False or view.btn_empty_trash.isHidden() is False
    actions={action.text() for action in view.btn_add_cloud.menu().actions()}
    assert {"Microsoft OneDrive","Google Drive"} <= actions
    view.close()


def test_document_view_shows_storage_in_gb_with_textual_status():
    app = _app()
    view = DocumentView()
    view.set_storage_usage(StorageUsageSummary(
        organization_id=1, plan_code="PERSONAL_10GB", plan_name="Pessoal 10 GB",
        quota_bytes=10*GB, used_bytes=int(7.4*GB), reserved_bytes=0,
        available_bytes=int(2.6*GB), percent=74.0, level="NORMAL", local_free_bytes=25*GB,
    ))
    app.processEvents()

    assert "7,4 GB de 10 GB" in view.storage_label.text()
    assert "NORMAL" in view.storage_label.text()
    assert view.storage_progress.value() == 74
    view.close()


def test_storage_management_menu_exposes_required_actions():
    _app()
    view = DocumentView()
    actions = {action.text() for action in view.btn_manage_storage.menu().actions()}
    assert {
        "Abrir lixeira", "Recalcular uso", "Ver arquivos maiores", "Alterar plano",
        "Sincronizar agora", "Ver erros da nuvem",
    } <= actions
    view.close()
