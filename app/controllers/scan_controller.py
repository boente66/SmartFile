from pathlib import Path

from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtWidgets import QMessageBox, QFileDialog

from app.views.scan_view import ScanView
from app.models.scan_config_model import ScanConfigModel
from app.services.scan_service import ScanService
from app.services.scan_pdf_service import ScanPDFService




class ScanController:
    """
    Controller do Scanner.
    """

    def __init__(self, workspace):
        self.workspace = workspace
        self.view = ScanView()

        # Estado mínimo: imagens PIL
        self._images = []
        self._devices_loaded = False

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

    def _register_view(self):
        self.workspace.register_view("scanner", self.view)

    def _load_devices(self):
        devices = ScanService.list_devices()
        self.view.set_devices(devices)
        self._devices_loaded = True

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
                color_mode=cfg["color"]
            )
            config.validate()
            img = ScanService.scan_page(config)
            self._images.append(img)

            rgb_image = img.convert("RGB")
            data = rgb_image.tobytes("raw", "RGB")
            qimage = QImage(
                data,
                img.width,
                img.height,
                img.width * 3,
                QImage.Format.Format_RGB888
            ).copy()
            rgb_image.close()
            pixmap = QPixmap.fromImage(qimage)

            self.view.add_thumbnail(pixmap)

        except Exception as e:
            QMessageBox.critical(
                self.view,
                "Erro ao escanear",
                str(e)
            )

    def on_remove_requested(self, index: int):
        if 0 <= index < len(self._images):
            self._images.pop(index).close()
            self.view.remove_thumbnail(index)

    def on_clear_requested(self):
        for image in self._images:
            image.close()
        self._images.clear()
        self.view.clear_pages()

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
