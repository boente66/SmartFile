from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PyQt6.QtWidgets import QApplication, QWidget

from app.controllers.pdf_viewer_controller import PDFViewerController
from app.errors.pdf_viewer_exceptions import (
    InvalidPDFError,
    PDFInvalidPasswordError,
    PDFPasswordRequiredError,
)
from app.models.pdf_document_info import PDFDocumentInfo
from app.models.pdf_render_request import PDFRenderRequest
from app.models.pdf_viewer_context import PDFViewerContext
from app.services.pdf_viewer_service import PDFViewerService
from app.views.pdf_viewer_view import PDFViewerView
from app.views.workspace_view import WorkspaceView
from app.workers.pdf_render_worker import PDFRenderWorker

_APPLICATION: QApplication | None = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _pdf(path: Path, pages: int = 2, text: str = "SmartFile") -> Path:
    document = fitz.open()
    for index in range(pages):
        page = document.new_page(width=300, height=500)
        page.insert_text((40, 60), f"{text} página {index + 1}")
    document.set_metadata({"title": "Documento de teste", "author": "SmartFile"})
    document.save(path)
    document.close()
    return path


def test_service_opens_valid_pdf_and_reads_information(tmp_path: Path):
    path = _pdf(tmp_path / "valid.pdf", pages=3)
    service = PDFViewerService()

    info = service.document_info(path)

    assert info.page_count == 3
    assert info.title == "Documento de teste"
    assert info.author == "SmartFile"
    assert info.page_width == 300


def test_service_rejects_missing_non_pdf_and_invalid_pdf(tmp_path: Path):
    service = PDFViewerService()
    with pytest.raises(InvalidPDFError):
        service.document_info(tmp_path / "missing.pdf")
    text = tmp_path / "file.txt"
    text.write_text("not pdf")
    with pytest.raises(InvalidPDFError):
        service.document_info(text)
    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"invalid")
    with pytest.raises(InvalidPDFError):
        service.document_info(invalid)


def test_password_protected_pdf_requires_correct_password(tmp_path: Path):
    plain = _pdf(tmp_path / "plain.pdf", pages=1)
    protected = tmp_path / "protected.pdf"
    document = fitz.open(plain)
    document.save(
        protected,
        encryption=fitz.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="user-secret",
    )
    document.close()
    service = PDFViewerService()

    with pytest.raises(PDFPasswordRequiredError):
        service.document_info(protected)
    with pytest.raises(PDFInvalidPasswordError):
        service.document_info(protected, "wrong")
    assert service.document_info(protected, "user-secret").page_count == 1


def test_render_zoom_rotation_highlight_and_cache(tmp_path: Path):
    path = _pdf(tmp_path / "render.pdf", pages=1)
    service = PDFViewerService(cache_size=2)
    normal = service.render_page(PDFRenderRequest(path, 1, zoom=1.0))
    rotated = service.render_page(PDFRenderRequest(path, 1, zoom=1.0, rotation=90))
    highlighted = service.render_page(
        PDFRenderRequest(path, 1, zoom=1.0, highlights=((35, 40, 160, 70),))
    )

    assert (normal.width(), normal.height()) == (300, 500)
    assert (rotated.width(), rotated.height()) == (500, 300)
    assert not highlighted.isNull()
    service.render_page(PDFRenderRequest(path, 1, zoom=1.0))
    assert len(service._cache) <= 2


def test_search_finds_text_and_reports_no_results(tmp_path: Path):
    path = _pdf(tmp_path / "search.pdf", pages=3, text="Contrato SmartFile")
    service = PDFViewerService()

    results = service.search(path, "Contrato")

    assert [page for page, _rectangles in results] == [1, 2, 3]
    assert service.search(path, "inexistente") == []


def test_thumbnail_uses_low_resolution_with_valid_zoom(tmp_path: Path):
    path = _pdf(tmp_path / "thumbnail.pdf", pages=1)

    image = PDFViewerService().render_thumbnail(path, 1)

    assert (image.width(), image.height()) == (75, 125)


def test_navigation_and_zoom_are_bounded_and_pdf_tools_key_is_preserved(tmp_path: Path):
    _app()
    workspace = WorkspaceView()
    controller = PDFViewerController(workspace)
    controller._info = PDFDocumentInfo(
        path=tmp_path / "x.pdf", name="x.pdf", size=1, page_count=8,
        page_width=300, page_height=500,
    )
    controller._render_current = lambda: None

    controller.go_to_page(0)
    assert controller._page == 1
    controller.go_to_page(99)
    assert controller._page == 8
    controller.set_zoom(0.1)
    assert controller._zoom == controller.MIN_ZOOM
    controller.set_zoom(9)
    assert controller._zoom == controller.MAX_ZOOM
    assert "pdf_viewer" in workspace.list_views()
    assert "finished" not in PDFRenderWorker.__dict__
    workspace.close()


def test_toolbar_uses_icons_without_clipping_at_workspace_width():
    app = _app()
    view = PDFViewerView()
    view.resize(1160, 700)
    view.show()
    app.processEvents()

    assert view._compact_toolbar is True
    assert all(button.text() == "" for button in view.buttons)
    assert all(button.width() == 38 for button in view.buttons)
    assert all(button.toolTip() for button in view.buttons)
    assert view.toolbar.sizeHint().width() <= view.width()

    view.resize(1700, 700)
    app.processEvents()
    assert view._compact_toolbar is False
    assert view.btn_sign.text() == "Assinar digitalmente"
    view.close()


def test_back_button_returns_to_documents_and_remains_available():
    app = _app()
    workspace = WorkspaceView()
    documents = QWidget()
    workspace.register_view("documents", documents)
    controller = PDFViewerController(workspace)
    controller.activate()
    controller.view.set_document_loaded(False)

    assert controller.view.btn_back.isEnabled()
    assert controller.view.btn_open.isEnabled()
    assert not controller.view.btn_back.icon().isNull()

    controller.view.btn_back.click()
    app.processEvents()

    assert workspace.current_view() == "documents"
    workspace.close()


def test_delivery_context_is_compact_and_returns_to_received_tab(tmp_path: Path):
    app = _app()
    workspace = WorkspaceView()
    documents = QWidget()

    class Deliveries(QWidget):
        selected = None

        def select_tab(self, value):
            self.selected = value

    deliveries = Deliveries()
    workspace.register_view("documents", documents)
    workspace.register_view("deliveries", deliveries)
    controller = PDFViewerController(workspace)
    context = PDFViewerContext(
        kind="DELIVERY_RECEIVED", protocol_number="SF-20260824-000001-ABCD",
        sender_name="Remetente", delivery_id=7, back_view="deliveries",
        back_tab="received", items=[("contrato.pdf", tmp_path / "contrato.pdf")],
        can_acknowledge=True,
    )
    controller._context = context
    controller.view.set_context(context)
    controller.activate()

    assert controller.view.context_bar.isVisibleTo(controller.view)
    assert controller.view.context_confirm.isVisibleTo(controller.view)
    assert "SF-20260824" in controller.view.context_detail.text()
    controller.return_to_documents()
    app.processEvents()

    assert workspace.current_view() == "deliveries"
    assert deliveries.selected == "received"
    workspace.close()


def test_first_successful_render_emits_document_displayed_once(tmp_path: Path):
    _app()
    workspace = WorkspaceView()
    controller = PDFViewerController(workspace)
    path = tmp_path / "received.pdf"
    controller._path = path
    controller._info = PDFDocumentInfo(
        path=path, name=path.name, size=1, page_count=1,
        page_width=300, page_height=500,
    )
    worker = object()
    controller._render_worker = worker
    controller._preload_adjacent = lambda: None
    displayed = []
    controller.view.document_displayed.connect(displayed.append)
    image = PDFViewerService().render_page(
        PDFRenderRequest(_pdf(path, pages=1), 1, zoom=1.0)
    )

    controller._on_rendered(worker, PDFRenderRequest(path, 1), image)
    controller._on_rendered(worker, PDFRenderRequest(path, 1), image)

    assert displayed == [str(path)]
    workspace.close()
