from PyQt6.QtCore import QThread, pyqtSignal

from app.services.handwritten_signature_service import HandwrittenSignatureService


class HandwrittenSignatureWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: HandwrittenSignatureService, request):
        super().__init__()
        self.service = service
        self.request = request

    def run(self):
        try:
            self.progress.emit(15, "Validando assinatura manuscrita")
            result = self.service.apply(self.request)
            self.progress.emit(100, "PDF salvo")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.request.signature_image = b""
