from PyQt6.QtCore import QThread, pyqtSignal

from app.services.scan_service import ScanService


class ScanWorker(QThread):
    """Executa a captura do scanner fora da thread da interface."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self) -> None:
        try:
            self.progress.emit(10, "Iniciando digitalização")
            image = ScanService.scan_page(self.config)
            self.progress.emit(100, "Página digitalizada")
            self.succeeded.emit(image)
        except Exception as exc:
            self.failed.emit(ScanService.friendly_error(exc, self.config.source_name))
