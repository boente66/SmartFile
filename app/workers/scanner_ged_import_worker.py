from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.scan_pdf_service import ScanPDFService


class ScannerGedImportWorker(QThread):
    """Gera o PDF temporário e o importa pelo núcleo documental em background."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, images, temporary: Path, document_service, metadata: dict, parent=None):
        super().__init__(parent)
        self.images = list(images)
        self.temporary = Path(temporary)
        self.document_service = document_service
        self.metadata = dict(metadata)

    def run(self) -> None:
        try:
            self.progress.emit(15, "Gerando PDF da digitalização")
            ScanPDFService.save_as_pdf(self.images, self.temporary)
            self.progress.emit(45, "Verificando armazenamento")
            document = self.document_service.import_document(
                str(self.temporary), **self.metadata
            )
            self.progress.emit(100, "Documento adicionado ao GED")
            self.succeeded.emit(document)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.temporary.unlink(missing_ok=True)
