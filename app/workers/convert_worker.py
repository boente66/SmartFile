from PyQt6.QtCore import QThread, pyqtSignal as Signal
from app.services.convert_service import ConvertService


class ConvertWorker(QThread):
    progress = Signal(int, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            ConvertService.execute(
                job=self.job,
                progress_callback=self._on_progress
            )
            self.finished.emit()

        except Exception as e:
            self.failed.emit(str(e))

    def _on_progress(self, value: int, message: str):
        self.progress.emit(value, message)
