from PyQt6.QtCore import QThread, pyqtSignal
from app.services.audit_service import AuditService

from app.services.handwritten_signature_service import HandwrittenSignatureService


class HandwrittenSignatureWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service: HandwrittenSignatureService, request):
        super().__init__()
        self.service = service
        self.request = request
        validation = getattr(service, 'validation_service', None)
        self.audit_actor = validation.audit.capture(validation.active_organization_id()) if validation else None

    def run(self):
        with AuditService.bind(self.audit_actor):
            self._run_operation()

    def _run_operation(self):
        try:
            self.progress.emit(15, "Validando assinatura manuscrita")
            result = self.service.apply(self.request)
            self.progress.emit(100, "PDF salvo")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.request.signature_image = b""
