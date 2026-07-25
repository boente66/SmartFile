import logging

from PyQt6.QtCore import QThread, pyqtSignal
from app.services.convert_service import ConvertService
from app.errors.conversion_exceptions import ConversionCancelledError

logger = logging.getLogger(__name__)


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        try:
            ConvertService.execute(
                job=self.job,
                progress_callback=self._on_progress,
                cancellation_callback=self.isInterruptionRequested,
            )
            if not self.job.output_path.is_file():
                raise RuntimeError(
                    "A conversão terminou sem produzir o arquivo de saída."
                )
            self.succeeded.emit()
        except ConversionCancelledError:
            self._cleanup_cancelled_outputs()
            self.cancelled.emit()
        except Exception as e:
            logger.exception(
                "conversion.worker.failed source=%s target=%s",
                self.job.source_format,
                self.job.target_format,
            )
            self.failed.emit(str(e))

    def _on_progress(self, value: int, message: str):
        self.progress.emit(value, message)

    def _cleanup_cancelled_outputs(self) -> None:
        candidates = [self.job.output_path]
        if self.job.target_format.upper() == "JPG":
            candidates.extend(
                self.job.output_path.parent.glob(
                    f"{self.job.output_path.stem}_*.jpg"
                )
            )
        for path in candidates:
            try:
                if path.is_file():
                    path.unlink()
            except OSError:
                logger.warning(
                    "conversion.cancel_cleanup_failed output=%s", path
                )
