from PyQt6.QtCore import QThread, pyqtSignal

from app.services.pdf_signature_service import PDFSignatureService


class PDFSignatureValidationWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: PDFSignatureService, path):
        super().__init__()
        self.service = service
        self.path = path

    def run(self):
        try:
            self.progress.emit(10, "Validando assinaturas")
            result = self.service.validate(self.path)
            self.progress.emit(100, "Validação concluída")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
