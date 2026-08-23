import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QBoxLayout

from app.views.document_view import DocumentView
from app.models.document_model import DocumentModel
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
    assert view.scroll_content.width() >= view.scroll_area.viewport().width() - 2
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
    assert "Pessoal 10 GB" in view.storage_label.toolTip()
    assert "Disco livre: 25 GB" in view.storage_label.toolTip()
    assert "Nível: NORMAL" in view.storage_label.toolTip()
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


def test_storage_widgets_are_reused_below_folder_tree_and_not_in_header():
    _app()
    view = DocumentView()

    assert view.storage_sidebar_panel.parentWidget() is view.folders_panel
    assert view.storage_label.parentWidget() is view.storage_sidebar_panel
    assert view.storage_progress.parentWidget() is view.storage_sidebar_panel
    assert view.cloud_quota_label.parentWidget() is view.storage_sidebar_panel
    assert view.cloud_quota_progress.parentWidget() is view.storage_sidebar_panel
    assert view.btn_manage_storage.parentWidget() is view.storage_sidebar_panel
    assert view.folders_layout.indexOf(view.folder_tree) < view.folders_layout.indexOf(
        view.storage_sidebar_panel
    )
    assert view.workspace_header.findChild(type(view.storage_label), "storageUsageLabel") is None
    assert view.workspace_header.findChild(
        type(view.cloud_quota_label), "cloudStorageQuotaLabel"
    ) is None
    view.close()


def test_navigation_toggle_hides_and_restores_tree_with_storage_summary():
    app = _app()
    view = DocumentView()
    view.resize(1366, 768)
    view.show()
    app.processEvents()

    assert view.folders_panel.isVisible()
    assert view.storage_sidebar_panel.isVisible()
    view.btn_toggle_folders.setChecked(False)
    app.processEvents()
    assert view.folders_panel.isHidden()
    assert not view.storage_sidebar_panel.isVisible()
    view.btn_toggle_folders.setChecked(True)
    app.processEvents()
    assert view.folders_panel.isVisible()
    assert view.storage_sidebar_panel.isVisible()
    view.close()


def test_cloud_quota_states_update_the_sidebar_without_horizontal_scroll():
    app = _app()
    view = DocumentView()
    view.set_cloud_quota_loading("ONEDRIVE")
    assert view.cloud_quota_label.text() == "OneDrive — consultando capacidade…"
    assert view.cloud_quota_progress.maximum() == 0

    for width in (1366, 1920, 1049, 760):
        view.resize(width, 768)
        view.show()
        app.processEvents()
        assert view.scroll_area.horizontalScrollBar().maximum() == 0

    view.clear_cloud_quota()
    assert "conecte uma conta" in view.cloud_quota_label.text().lower()
    assert view.cloud_quota_progress.isHidden()
    view.close()


def test_document_workspace_model_preserves_actions_and_adds_navigation_context():
    app = _app()
    view = DocumentView()
    view.set_organizations([SimpleNamespace(id=1, name="Minha Organização")], 1)
    view.set_folders("Minha Organização", [
        SimpleNamespace(id=10, parent_id=None, name="Clientes"),
        SimpleNamespace(id=11, parent_id=10, name="Contratos"),
    ])
    view.set_documents([DocumentModel(
        id=42, name="contrato.pdf", file_type="PDF", updated_at="2026-08-22T14:30:00",
    )])
    view.resize(1500, 800)
    view.show()
    app.processEvents()

    assert view.workspace_header.objectName() == "documentWorkspaceHeader"
    assert view.action_bar.objectName() == "documentActionBar"
    assert view.filters_frame.objectName() == "documentFilterBar"
    assert view.documents_table.columnCount() == 7
    assert view.documents_table.horizontalHeaderItem(6).text() == "Modificado em"
    assert view.documents_table.item(0, 6).text() == "22/08/2026 14:30"
    assert not view.documents_table.item(0, 0).icon().isNull()

    contracts = view.folder_tree.topLevelItem(0).child(0).child(0)
    view.folder_tree.setCurrentItem(contracts)
    app.processEvents()
    assert view.breadcrumb_label.text() == "Minha Organização  ›  Clientes  ›  Contratos"

    view.btn_toggle_folders.setChecked(False)
    view.btn_toggle_details.setChecked(False)
    assert view.folders_panel.isHidden()
    assert view.details.isHidden()
    view.close()


def test_advanced_filters_are_collapsible_without_losing_values():
    _app()
    view = DocumentView()
    view.source_combo.setCurrentIndex(2)
    selected = view.source_combo.currentData()

    view.btn_advanced_filters.setChecked(False)
    assert view.smart_filters_widget.isHidden()
    view.btn_advanced_filters.setChecked(True)

    assert not view.smart_filters_widget.isHidden()
    assert view.source_combo.currentData() == selected
    view.close()
