from PyQt6.QtCore import QThread, pyqtSignal


class CloudSyncWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, sync_service, organization_id: int):
        super().__init__()
        self.sync_service = sync_service
        self.organization_id = organization_id

    def run(self):
        try:
            self.progress.emit(10, "Consultando alterações remotas")
            changes = self.sync_service.sync_changes(self.organization_id)
            processed = 0
            while not self.isInterruptionRequested() and self.sync_service.queue.next_pending(self.organization_id):
                self.sync_service.process_next(self.organization_id)
                processed += 1
                self.progress.emit(min(90, 20 + processed * 10), "Processando fila de sincronização")
            self.progress.emit(100, "Sincronização concluída")
            self.succeeded.emit({"changes": changes, "jobs": processed})
        except Exception as exc:
            self.failed.emit(str(exc))
