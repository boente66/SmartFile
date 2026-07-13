from PyQt6.QtCore import QThread, pyqtSignal


class CloudUploadWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sync_service, document_id: int, organization_id: int):
        super().__init__()
        self.sync_service = sync_service
        self.document_id = document_id
        self.organization_id = organization_id

    def run(self):
        try:
            self.progress.emit(10, "Adicionando upload à fila")
            job = self.sync_service.enqueue_upload(self.document_id, self.organization_id)
            if job is not None:
                self.progress.emit(40, "Enviando documento")
                self.sync_service.process_next()
            self.progress.emit(100, "Sincronização processada")
            self.succeeded.emit(job)
        except Exception as exc:
            self.failed.emit(str(exc))
