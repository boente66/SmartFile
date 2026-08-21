from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class LanDiscoveryWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, timeout: float = 3.0, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.timeout = timeout

    def run(self) -> None:
        try:
            self.progress.emit(10, "Procurando SmartFiles na rede local...")
            devices = self.service.discover(
                self.timeout, cancelled=self.isInterruptionRequested,
            )
            if self.isInterruptionRequested():
                self.progress.emit(100, "Busca cancelada.")
                self.succeeded.emit([])
                return
            self.progress.emit(100, "Busca concluída.")
            self.succeeded.emit(devices)
        except Exception as exc:
            self.failed.emit(str(exc))


class LanConnectionWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, instance_service, peer, parent=None) -> None:
        super().__init__(parent)
        self.instance_service = instance_service
        self.peer = peer

    def run(self) -> None:
        try:
            self.succeeded.emit(self.instance_service.test_connection(self.peer))
        except Exception as exc:
            self.failed.emit(str(exc))
