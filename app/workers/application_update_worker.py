from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class ApplicationUpdateWorker(QThread):
    update_available = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service):
        super().__init__()
        self.service = service

    def run(self) -> None:
        try:
            update = self.service.check()
            if update is not None:
                self.update_available.emit(update)
        except Exception as exc:
            logger.info("application.update.check_failed error=%s", type(exc).__name__)
            self.failed.emit("Não foi possível verificar atualizações agora.")
