from PyQt6.QtCore import QThread, pyqtSignal


class DocumentValidationWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            result = self.operation(self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
