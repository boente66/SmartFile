from PyQt6.QtCore import QThread, pyqtSignal

from app.services.pdf_signature_service import PDFSignatureService


class PDFSignatureWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: PDFSignatureService, request):
        super().__init__()
        self.service = service
        self.request = request

    def run(self):
        try:
            self.progress.emit(10, "Carregando certificado")
            result = self.service.sign(self.request)
            self.progress.emit(100, "PDF assinado")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
