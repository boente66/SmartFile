import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtWidgets import QApplication, QDialog

from app.controllers.scan_controller import ScanController
from app.services.document_service import DocumentService
from app.views.scanner_import_dialog import ScannerImportDialog


_APP = None


class _Workspace:
    def register_view(self, name, view):
        self.name = name
        self.view = view

    def show_view(self, _name):
        pass


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_scanner_adds_pdf_directly_to_ged_and_removes_temporary(tmp_path: Path, monkeypatch):
    _app()
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    controller = ScanController(_Workspace(), service)
    controller._images = [Image.new("RGB", (20, 20), "white"), Image.new("RGB", (20, 20), "black")]
    monkeypatch.setattr(ScannerImportDialog, "exec", lambda _self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(
        ScannerImportDialog, "values",
        lambda _self: {
            "organization_id": service.active_organization_id, "folder_id": None,
            "title": "Digitalização direta", "category": "Documento", "description": None,
            "tags": "scanner", "document_date": "2026-07-13", "notes": None,
            "source_type": "SCANNER", "sync_cloud": True,
        },
    )
    monkeypatch.setattr("app.controllers.scan_controller.QMessageBox.information", lambda *_args: None)
    monkeypatch.setattr("app.controllers.scan_controller.QMessageBox.warning", lambda *_args: None)

    controller.on_add_to_ged_requested()
    worker = controller._ged_worker
    assert worker is not None
    assert worker.wait(5000)
    _app().processEvents()

    documents = service.list_documents()
    assert len(documents) == 1
    assert documents[0].source_type == "SCANNER"
    assert Path(documents[0].storage_path).is_file()
    assert not list(service.database.paths.temp.glob("scanner-*.pdf"))
    assert controller._images == []
    controller.view.close()


def test_scanner_ged_worker_keeps_native_finished_signal():
    from app.workers.scanner_ged_import_worker import ScannerGedImportWorker
    assert "finished" not in ScannerGedImportWorker.__dict__
