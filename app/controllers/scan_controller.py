from pathlib import Path

from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QMessageBox, QFileDialog, QDialog
from uuid import uuid4

from app.views.scan_view import ScanView
from app.models.scan_config_model import ScanConfigModel
from app.services.scan_service import ScanService
from app.services.scan_pdf_service import ScanPDFService
from app.services.document_service import DocumentService
from app.views.scanner_import_dialog import ScannerImportDialog
from app.workers.scan_worker import ScanWorker
from app.workers.scanner_ged_import_worker import ScannerGedImportWorker




class ScanController:
    """
    Controller do Scanner.
    """

    def __init__(self, workspace, document_service: DocumentService | None = None, imported_callback=None, session_context=None):
        self.workspace = workspace
        self.view = ScanView()
        self.document_service = document_service
        self.imported_callback = imported_callback
        self.session_context = session_context

        # Estado mínimo: imagens PIL
        self._images = []
        self._devices_loaded = False
        self._scan_worker = None
        self._ged_worker = None

        self._connect_signals()
        self._register_view()

    # -------------------------
    # Inicialização
    # -------------------------
    def _connect_signals(self):
        self.view.scan_requested.connect(self.on_scan_requested)
        self.view.remove_requested.connect(self.on_remove_requested)
        self.view.save_pdf_requested.connect(self.on_save_pdf_requested)
        self.view.clear_requested.connect(self.on_clear_requested)
        self.view.refresh_devices_requested.connect(self._load_devices)
        self.view.device_changed.connect(self._load_sources)
        self.view.add_to_ged_requested.connect(self.on_add_to_ged_requested)
        self.view.reorder_requested.connect(self.on_reorder_requested)

    def _register_view(self):
        self.workspace.register_view("scanner", self.view)

    def _load_devices(self):
        devices = ScanService.list_devices()
        self.view.set_devices(devices)
        self._devices_loaded = True

    def _load_sources(self, device_name: str):
        if not device_name or device_name == "Nenhum scanner encontrado":
            self.view.set_sources([])
            return
        self.view.set_sources(ScanService.list_sources(device_name))

    # -------------------------
    # API pública
    # -------------------------
    def activate(self):
        self.workspace.show_view("scanner")
        if not self._devices_loaded:
            self._load_devices()


    # -------------------------
    # Slots
    # -------------------------
    def on_scan_requested(self):
        cfg = self.view.get_scan_config()

        if not cfg["device"]:
            QMessageBox.warning(
                self.view,
                "Scanner",
                "Selecione um scanner."
            )
            return

        try:
            config = ScanConfigModel(
                device_name=cfg["device"],
                dpi=cfg["dpi"],
                color_mode=cfg["color"],
                source_name=cfg["source"],
            )
            config.validate()
            if self._scan_worker is not None:
                QMessageBox.information(self.view, "Scanner", "Aguarde a digitalização atual.")
                return
            worker = ScanWorker(config)
            self._scan_worker = worker
            worker.succeeded.connect(self._on_scan_succeeded)
            worker.failed.connect(self._on_scan_failed)
            worker.finished.connect(lambda worker=worker: self._cleanup_scan_worker(worker))
            worker.finished.connect(worker.deleteLater)
            self.view.set_scan_busy(True)
            worker.start()

        except Exception as e:
            QMessageBox.critical(
                self.view,
                "Erro ao escanear",
                ScanService.friendly_error(e, cfg.get("source"))
            )

    def _on_scan_succeeded(self, img):
        self._images.append(img)
        rgb_image = img.convert("RGB")
        try:
            data = rgb_image.tobytes("raw", "RGB")
            qimage = QImage(
                data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888
            ).copy()
            self.view.add_thumbnail(QPixmap.fromImage(qimage))
        finally:
            rgb_image.close()

    def _on_scan_failed(self, message: str):
        QMessageBox.critical(self.view, "Erro ao escanear", message)

    def _cleanup_scan_worker(self, worker):
        if self._scan_worker is worker:
            self._scan_worker = None
            self.view.set_scan_busy(False)

    def on_remove_requested(self, index: int):
        if 0 <= index < len(self._images):
            self._images.pop(index).close()
            self.view.remove_thumbnail(index)

    def on_clear_requested(self):
        for image in self._images:
            image.close()
        self._images.clear()
        self.view.clear_pages()

    def on_reorder_requested(self, source: int, target: int):
        if 0 <= source < len(self._images) and 0 <= target < len(self._images):
            image = self._images.pop(source)
            self._images.insert(target, image)
            self.view.move_thumbnail(source, target)

    def on_add_to_ged_requested(self):
        if not self._images:
            QMessageBox.warning(self.view, "Adicionar ao GED", "Nenhuma página digitalizada.")
            return
        if self.document_service is None:
            QMessageBox.warning(self.view, "Adicionar ao GED", "Serviço documental indisponível.")
            return
        allowed = None
        if self.session_context and self.session_context.is_authenticated():
            allowed = [item.organization_id for item in self.session_context.memberships]
        dialog = ScannerImportDialog(
            self.document_service, self.view, allowed_organization_ids=allowed
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self._ged_worker is not None:
            QMessageBox.information(self.view, "Adicionar ao GED", "Já existe uma importação em andamento.")
            return
        temporary = self.document_service.database.paths.temp / f"scanner-{uuid4()}.pdf"
        worker = ScannerGedImportWorker(
            self._images, temporary, self.document_service, dialog.values()
        )
        self._ged_worker = worker
        worker.succeeded.connect(self._on_ged_import_succeeded)
        worker.failed.connect(self._on_ged_import_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup_ged_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self.view.set_import_busy(True)
        worker.start()

    def _on_ged_import_succeeded(self, document):
        self.on_clear_requested()
        if self.imported_callback:
            self.imported_callback()
        QMessageBox.information(
            self.view, "Adicionar ao GED", f"Documento adicionado com sucesso: {document.name}"
        )

    def _on_ged_import_failed(self, message: str):
        QMessageBox.warning(self.view, "Adicionar ao GED", message)

    def _cleanup_ged_worker(self, worker):
        if self._ged_worker is worker:
            self._ged_worker = None
            self.view.set_import_busy(False)

    def on_save_pdf_requested(self):
        if not self._images:
            QMessageBox.warning(
                self.view,
                "Salvar PDF",
                "Nenhuma página escaneada."
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Salvar PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if not path:
            return

        try:
            ScanPDFService.save_as_pdf(
                images=self._images,
                output_file=Path(path)
            )

            QMessageBox.information(
                self.view,
                "Sucesso",
                "PDF salvo com sucesso."
            )

        except Exception as e:
            QMessageBox.critical(
                self.view,
                "Erro ao salvar PDF",
                str(e)
            )
