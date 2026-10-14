from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal
from app.services.audit_service import AuditService


class FileOperationWorker(QThread):
    """Executa uma operação custosa da sessão sem bloquear a interface."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, task: Callable[[Callable[[int, str], None], Callable[[], bool]], object], parent=None, *, audit_actor=None):
        super().__init__(parent)
        self._task = task
        self.audit_actor = audit_actor

    def run(self) -> None:
        with AuditService.bind(self.audit_actor):
            self._run_task()

    def _run_task(self) -> None:
        try:
            result = self._task(
                self.progress.emit,
                self.isInterruptionRequested,
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
            else:
                self.cancelled.emit()
        except InterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            if self.isInterruptionRequested():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc) or "A operação não pôde ser concluída.")
