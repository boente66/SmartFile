import logging

from PyQt6.QtCore import QThread, pyqtSignal
from app.services.convert_service import ConvertService
from app.services.audit_service import AuditService
from app.errors.conversion_exceptions import ConversionCancelledError

logger = logging.getLogger(__name__)


class ConvertWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, job, *, document_service=None):
        super().__init__()
        self.job = job
        self.documents=document_service
        self.audit_actor=document_service.audit.capture(document_service.active_organization_id) if document_service else None

    def run(self):
        with AuditService.bind(self.audit_actor):
            self._run_conversion()

    def _run_conversion(self):
        try:
            outputs = ConvertService.execute(
                job=self.job,
                progress_callback=self._on_progress,
                cancellation_callback=self.isInterruptionRequested,
            )
            if not self.job.output_path.is_file():
                raise RuntimeError(
                    "A conversão terminou sem produzir o arquivo de saída."
                )
            if self.documents is not None:
                for output in outputs or (self.job.output_path,):
                    self.documents.record_output(output, (self.job.input_path,),
                        action='CONVERT', source_type='CONVERTER')
            self.succeeded.emit()
        except ConversionCancelledError:
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
