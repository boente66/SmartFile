from PyQt6.QtCore import QThread, pyqtSignal

from app.models.pdf_render_request import PDFRenderRequest
from app.services.pdf_viewer_service import PDFViewerService


class PDFRenderWorker(QThread):
    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(str)

    def __init__(self, service: PDFViewerService, request: PDFRenderRequest):
        super().__init__()
        self.service = service
        self.request = request

    def run(self):
        try:
            image = self.service.render_page(self.request)
            if not self.isInterruptionRequested():
                self.succeeded.emit(self.request, image)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
