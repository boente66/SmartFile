from PyQt6.QtCore import QThread, pyqtSignal


class CloudAuthWorker(QThread):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, service, provider: str):
        super().__init__(); self.service=service; self.provider=provider

    def run(self):
        try:
            self.progress.emit(10,"Abrindo autenticação no navegador")
            result=self.service.authenticate(self.provider)
            self.progress.emit(100,"Autenticação concluída")
            self.succeeded.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
