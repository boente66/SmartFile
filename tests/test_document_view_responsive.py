import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QBoxLayout

from app.views.document_view import DocumentView

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
