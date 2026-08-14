from __future__ import annotations

from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal


class CapturePdfWorker(QThread):
    """Executa uma operação custosa da sessão sem bloquear a interface."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable[[Callable[[int, str], None], Callable[[], bool]], object], parent=None):
        super().__init__(parent)
        self._task = task

    def run(self) -> None:
        try:
            result = self._task(
                self.progress.emit,
                self.isInterruptionRequested,
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except InterruptedError:
            return
        except Exception as exc:
            self.failed.emit(str(exc) or "A operação não pôde ser concluída.")
