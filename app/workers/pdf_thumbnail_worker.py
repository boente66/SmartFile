from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.pdf_viewer_service import PDFViewerService


class PDFThumbnailWorker(QThread):
    thumbnail_ready = pyqtSignal(int, object)
    failed = pyqtSignal(str)

    def __init__(self, service: PDFViewerService, path: Path, pages: int, password=None):
        super().__init__()
        self.service = service
        self.path = path
        self.pages = pages
        self.password = password

    def run(self):
        try:
            for page_number in range(1, self.pages + 1):
                if self.isInterruptionRequested():
                    return
                image = self.service.render_thumbnail(self.path, page_number, self.password)
                self.thumbnail_ready.emit(page_number, image)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
