from PyQt6.QtCore import QThread, pyqtSignal


class BackupWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, destination, parent=None):
        super().__init__(parent)
        self.service = service
        self.destination = destination

    def run(self):
        try:
            result = self.service.create_full_backup(
                self.destination, lambda value, message: self.progress.emit(value, message)
            )
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
