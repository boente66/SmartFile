from PyQt6.QtCore import QThread, pyqtSignal


class DeliverySendWorker(QThread):
    progress=pyqtSignal(int,str); succeeded=pyqtSignal(object); failed=pyqtSignal(str)
    def __init__(self, coordinator, delivery_id: int, parent=None): super().__init__(parent); self.coordinator=coordinator; self.delivery_id=delivery_id
    def run(self):
        try: self.succeeded.emit(self.coordinator.send_once(self.delivery_id,self.progress.emit,self.isInterruptionRequested))
        except InterruptedError: return
        except Exception as exc: self.failed.emit(str(exc))
