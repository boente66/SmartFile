from PyQt6.QtCore import QThread, pyqtSignal

from app.cloud.cloud_models import CloudOperation, CloudSyncState


class CloudDownloadWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sync_service, document):
        super().__init__()
        self.sync_service = sync_service
        self.document = document

    def run(self):
        try:
            self.progress.emit(10, "Adicionando download à fila")
            self.sync_service.documents.update_cloud_state(
                self.document.id, CloudSyncState.PENDING_DOWNLOAD,
                self.document.cloud_provider, self.document.remote_id,
            )
            job = self.sync_service.queue.enqueue(
                self.document.id, CloudOperation.DOWNLOAD, self.document.cloud_provider
            )
            self.sync_service.process_next(self.document.organization_id)
            self.progress.emit(100, "Download concluído")
            self.succeeded.emit(job)
        except Exception as exc:
            self.failed.emit(str(exc))
