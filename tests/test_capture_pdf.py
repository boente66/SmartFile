from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PIL import Image
from PyQt6.QtCore import QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication, QDialog
from pypdf import PdfReader

from app.controllers.capture_pdf_controller import CapturePdfController
from app.database.database import Database
from app.models.capture_pdf_workspace import CapturePdfWorkspace
from app.services.capture_pdf_service import CapturePdfService
from app.services.document_service import DocumentService
from app.views.capture_pdf_view import CapturePdfView
from app.views.workspace_view import WorkspaceView
from app.workers.capture_pdf_worker import CapturePdfWorker

_APPLICATION = None


def app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def make_pdf(path: Path, labels: list[str]) -> Path:
    document = fitz.open()
    for label in labels:
        page = document.new_page(width=220, height=300)
        page.insert_text((30, 80), label, fontsize=26)
    document.save(path)
    document.close()
    return path


def wait_until(predicate, timeout: int = 5000):
    application = app()
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    deadline = QTimer()
    deadline.setSingleShot(True)
    deadline.timeout.connect(loop.quit)
    timer.start(); deadline.start(timeout); loop.exec(); timer.stop()
    application.processEvents()
    assert predicate()


def test_workspace_reorders_abcd_to_dabc_and_materializes_that_order(tmp_path: Path):
    sources = [make_pdf(tmp_path / f"{label}.pdf", [label]) for label in "ABCD"]
    state = CapturePdfWorkspace()
    for source in sources:
        state.add_pages(CapturePdfService.pages_from_pdf(source))
    state.reorder([state.pages[3].id, state.pages[0].id, state.pages[1].id, state.pages[2].id])
    output = CapturePdfService.materialize(state.pages, tmp_path / "ordered.pdf")
    reader = PdfReader(output)
    assert [page.extract_text().strip() for page in reader.pages] == ["D", "A", "B", "C"]


def test_rotation_is_persisted_in_generated_pdf(tmp_path: Path):
    source = make_pdf(tmp_path / "source.pdf", ["ROTATE"])
    state = CapturePdfWorkspace(pages=CapturePdfService.pages_from_pdf(source), current_page=0)
    state.rotate([0], 90)
    output = CapturePdfService.materialize(state.pages, tmp_path / "rotated.pdf")
    assert int(PdfReader(output).pages[0].rotation) == 90


def test_import_image_open_and_add_pdf_then_extract(tmp_path: Path):
    image_path = tmp_path / "page.png"
    Image.new("RGB", (90, 120), "white").save(image_path)
    pages = CapturePdfService.pages_from_images([image_path])
    pages.extend(CapturePdfService.pages_from_pdf(make_pdf(tmp_path / "extra.pdf", ["PDF"])))
    output = CapturePdfService.materialize(pages, tmp_path / "combined.pdf")
    extracted = CapturePdfService.materialize([pages[1]], tmp_path / "extracted.pdf")
    assert len(PdfReader(output).pages) == 2
    assert PdfReader(extracted).pages[0].extract_text().strip() == "PDF"
    CapturePdfService.close_pages(pages)


def test_capture_view_exposes_single_workspace_actions_and_drag_state():
    application = app(); view = CapturePdfView()
    assert view.btn_scan.text() == "Iniciar Digitalização"
    assert view.btn_ged.text() == "Adicionar ao SmartFile..."
    assert view.page_list.dragDropMode().name == "InternalMove"
    assert view.page_list.selectionMode().name == "ExtendedSelection"
    view.set_devices(["Scanner Fake"])
    assert view.get_scan_config()["device"] == "Scanner Fake"
    view.resize(900, 600); view.show(); application.processEvents()
    assert view.splitter.count() == 3
    view.close()


def test_capture_worker_uses_native_finished_and_reports_failures():
    app(); messages = []; finished = []
    worker = CapturePdfWorker(lambda _progress, _cancelled: (_ for _ in ()).throw(RuntimeError("offline")))
    worker.failed.connect(messages.append); worker.finished.connect(lambda: finished.append(True))
    worker.start(); worker.wait(3000); app().processEvents()
    assert messages == ["offline"]
    assert finished == [True]


def test_fake_scan_adds_page_and_failure_preserves_existing_workspace(tmp_path: Path, monkeypatch):
    application = app(); database = Database(str(tmp_path / "smartfile.db"))
    controller = CapturePdfController(WorkspaceView(), DocumentService(database=database))
    controller._on_scan_succeeded(Image.new("RGB", (80, 100), "white"))
    wait_until(lambda: controller._render_worker is None)
    assert len(controller.state.pages) == 1
    monkeypatch.setattr("app.controllers.capture_pdf_controller.QMessageBox.critical", lambda *args: None)
    controller._on_scan_failed("Scanner offline")
    assert len(controller.state.pages) == 1
    controller.clear_workspace(confirm=False)


def test_controller_open_merge_reorder_rotate_remove_and_save(tmp_path: Path, monkeypatch):
    app(); database = Database(str(tmp_path / "smartfile.db")); workspace = WorkspaceView()
    controller = CapturePdfController(workspace, DocumentService(database=database))
    monkeypatch.setattr("app.controllers.capture_pdf_controller.QMessageBox.information", lambda *args: None)
    source = make_pdf(tmp_path / "base.pdf", ["A", "B"])
    extra = make_pdf(tmp_path / "extra.pdf", ["C"])
    controller.on_open_pdf(str(source)); wait_until(lambda: controller._operation_worker is None and controller._render_worker is None)
    controller.on_add_pdfs([str(extra)]); wait_until(lambda: controller._operation_worker is None and controller._render_worker is None)
    ids = [page.id for page in controller.state.pages]
    controller.on_reorder_pages([ids[2], ids[0], ids[1]]); wait_until(lambda: controller._render_worker is None)
    controller.on_rotate_pages([1], 90); wait_until(lambda: controller._render_worker is None)
    controller.on_remove_pages([2]); wait_until(lambda: controller._render_worker is None)
    output = tmp_path / "result.pdf"
    controller.on_save_pdf(str(output)); wait_until(lambda: controller._operation_worker is None)
    reader = PdfReader(output)
    assert [page.extract_text().strip() for page in reader.pages] == ["C", "A"]
    assert int(reader.pages[1].rotation) == 90
    controller.clear_workspace(confirm=False)


def test_controller_splits_every_workspace_page(tmp_path: Path, monkeypatch):
    app(); database = Database(str(tmp_path / "smartfile.db")); controller = CapturePdfController(WorkspaceView(), DocumentService(database=database))
    monkeypatch.setattr("app.controllers.capture_pdf_controller.QMessageBox.information", lambda *args: None)
    controller.state.add_pages(CapturePdfService.pages_from_pdf(make_pdf(tmp_path / "source.pdf", ["A", "B", "C"])))
    output = tmp_path / "split"
    controller.on_split_pdf(str(output)); wait_until(lambda: controller._operation_worker is None)
    files = sorted(output.glob("*.pdf"))
    assert len(files) == 3
    assert [PdfReader(path).pages[0].extract_text().strip() for path in files] == ["A", "B", "C"]
    controller.clear_workspace(confirm=False)


def test_ged_flow_uses_document_service_managed_storage(tmp_path: Path, monkeypatch):
    app(); database = Database(str(tmp_path / "smartfile.db")); service = DocumentService(database=database)
    controller = CapturePdfController(WorkspaceView(), service)
    controller.state.add_pages(CapturePdfService.pages_from_pdf(make_pdf(tmp_path / "ged.pdf", ["GED"])))
    class AcceptedDialog:
        title = type("Title", (), {"setText": lambda self, value: None})()
        def __init__(self, *args, **kwargs): pass
        def setWindowTitle(self, value): pass
        def exec(self): return QDialog.DialogCode.Accepted
        def values(self):
            return {"organization_id": service.active_organization_id, "folder_id": None, "title": "GED integrado", "category": "Documento", "description": None, "tags": None, "document_date": None, "notes": None, "source_type": "SCANNER", "sync_cloud": False}
    imported = []
    original = service.import_document
    def recording_import(path, **metadata):
        result = original(path, **metadata); imported.append((Path(path), metadata, result)); return result
    monkeypatch.setattr("app.controllers.capture_pdf_controller.ScannerImportDialog", AcceptedDialog)
    monkeypatch.setattr(service, "import_document", recording_import)
    monkeypatch.setattr("app.controllers.capture_pdf_controller.QMessageBox.information", lambda *args: None)
    controller.on_add_to_ged(); wait_until(lambda: controller._operation_worker is None)
    assert len(imported) == 1
    assert imported[0][1]["source_type"] == "PDF_TOOLS"
    document = service.get_document(imported[0][2].id)
    assert document is not None and document.managed is True
    assert Path(document.path).is_file()
    assert not list(database.paths.temp.glob("capture-pdf-*.pdf"))
    controller.clear_workspace(confirm=False)
