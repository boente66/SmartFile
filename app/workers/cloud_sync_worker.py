import logging

from PyQt6.QtCore import QThread, pyqtSignal

from app.cloud.cloud_provider import CloudError

logger = logging.getLogger(__name__)


class CloudSyncWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sync_service, organization_id: int):
        super().__init__()
        self.sync_service = sync_service
        self.organization_id = organization_id

    def run(self):
        result = None
        error_message = None
        try:
            logger.info(
                "cloud.sync.worker.start organization_id=%s",
                self.organization_id,
            )
            self.progress.emit(5, "Preparando sincronização")
            changes = self.sync_service.sync_changes(
                self.organization_id,
                lambda value, message: self.progress.emit(value, message),
            )
            processed = 0
            pending = self.sync_service.queue.pending_count(self.organization_id)
            self.progress.emit(40, "Processando fila de sincronização")
            while self.sync_service.queue.next_pending(self.organization_id):
                if self.isInterruptionRequested():
                    raise CloudError("A sincronização foi cancelada.")
                self.sync_service.process_next(self.organization_id)
                processed += 1
                value = 40 + int((processed / max(1, pending)) * 55)
                self.progress.emit(
                    min(95, value), "Processando fila de sincronização"
                )
                if processed >= 1000:
                    raise CloudError(
                        "A fila excedeu o limite seguro de operações por sincronização."
                    )
            self.progress.emit(100, "Sincronização concluída")
            result = {"changes": changes, "jobs": processed}
        except Exception as exc:
            logger.exception(
                "cloud.sync.worker.failed organization_id=%s",
                self.organization_id,
            )
            error_message = str(exc).strip() or "Falha inesperada na sincronização."
            try:
                self.sync_service.mark_pending_documents_failed(
                    self.organization_id, error_message
                )
            except Exception:
                logger.exception(
                    "cloud.sync.worker.failed_to_persist_error organization_id=%s",
                    self.organization_id,
                )
        finally:
            if error_message is not None:
                self.progress.emit(100, "Falha na sincronização")
                self.failed.emit(error_message)
            else:
                self.succeeded.emit(result)
            logger.info(
                "cloud.sync.worker.finished organization_id=%s success=%s",
                self.organization_id, error_message is None,
            )
