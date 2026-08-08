from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class TransportWorker(QThread):
    """Executa uma tarefa de transporte sem bloquear a thread da interface."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, task: Callable, parent=None):
        super().__init__(parent)
        self.task = task

    def run(self) -> None:
        try:
            result = self.task(
                lambda value, message: self.progress.emit(value, message),
                self.isInterruptionRequested,
            )
            self.succeeded.emit(result)
        except Exception as exc:
            logger.exception("corporate.transport.worker.failed")
            self.failed.emit(
                str(exc).strip() or "Falha inesperada no transporte corporativo."
            )
