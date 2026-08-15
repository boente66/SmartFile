from PyQt6.QtCore import QThread, pyqtSignal


class DeliveryQueueWorker(QThread):
    """Processa a fila persistente e consultas remotas fora da UI."""

    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, coordinator, parent=None):
        super().__init__(parent)
        self.coordinator = coordinator

    def run(self) -> None:
        try:
            self.coordinator.process_pending_sync(self.isInterruptionRequested)
            self.succeeded.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
