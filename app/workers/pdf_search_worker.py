from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.pdf_viewer_service import PDFViewerService


class PDFSearchWorker(QThread):
    succeeded = pyqtSignal(str, object)
    failed = pyqtSignal(str)

    def __init__(self, service: PDFViewerService, path: Path, term: str, password=None):
        super().__init__()
        self.service = service
        self.path = path
        self.term = term
        self.password = password

    def run(self):
        try:
            results = self.service.search(self.path, self.term, self.password)
            if not self.isInterruptionRequested():
                self.succeeded.emit(self.term, results)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
