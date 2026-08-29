from PyQt6.QtCore import QThread, pyqtSignal


class CloudAuthWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, provider: str, organization_id: int):
        super().__init__(); self.service=service; self.provider=provider
        self.organization_id = organization_id

    def run(self):
        try:
            self.progress.emit(10,"Abrindo autenticação no navegador")
            result=self.service.authenticate(
                self.provider, organization_id=self.organization_id
            )
            self.progress.emit(100,"Autenticação concluída")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
