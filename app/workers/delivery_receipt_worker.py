from PyQt6.QtCore import QThread, pyqtSignal


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

    def run(self):
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

