from PyQt6.QtCore import QThread, pyqtSignal


class RequestSendWorker(QThread):
    """Publica uma solicitação no peer sem bloquear a interface."""

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, coordinator, request_id: int, peer, parent=None):
        super().__init__(parent)
        self.coordinator = coordinator
        self.request_id = request_id
        self.peer = peer

    def run(self) -> None:
        try:
            self.succeeded.emit(
                self.coordinator.send_request(self.request_id, self.peer)
            )
        except Exception as exc:
            self.failed.emit(str(exc))
