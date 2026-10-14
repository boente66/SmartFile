from PyQt6.QtCore import QThread, pyqtSignal
from app.services.audit_service import AuditService


class DocumentValidationWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, operation, parent=None, *, audit_actor=None):
        super().__init__(parent)
        self.operation = operation
        self.audit_actor = audit_actor

    def run(self):
        with AuditService.bind(self.audit_actor):
            self._run_operation()

    def _run_operation(self):
        try:
            result = self.operation(self.isInterruptionRequested)
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except Exception as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
