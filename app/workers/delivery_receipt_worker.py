from PyQt6.QtCore import QThread, pyqtSignal
from app.services.audit_service import AuditService


class DeliveryReceiptWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, delivery_id, user_id, signature_image, method, parent=None):
        super().__init__(parent)
        self.service = service
        self.delivery_id = delivery_id
        self.user_id = user_id
        self.signature_image = signature_image
        self.method = method
        delivery = service.deliveries.find_by_id(delivery_id)
        self.audit_actor = service.audit.capture(delivery.organization_id, user_id=user_id) if delivery else None

    def run(self):
        with AuditService.bind(self.audit_actor):
            self._run_operation()

    def _run_operation(self):
        try:
            self.progress.emit(15, "Validando assinatura visual")
            receipt = self.service.create_acknowledgement_receipt(
                self.delivery_id, self.user_id, self.signature_image, self.method
            )
            self.progress.emit(100, "Comprovante PDF criado")
            self.succeeded.emit(receipt)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.signature_image = b""

