from pathlib import Path

from PyQt6.QtWidgets import QDialog, QMessageBox

from app.services.pdf_signature_service import PDFSignatureService
from app.views.pdf_signature_dialog import PDFSignatureDialog
from app.views.pdf_signature_validation_dialog import PDFSignatureValidationDialog
from app.workers.pdf_signature_validation_worker import PDFSignatureValidationWorker
from app.workers.pdf_signature_worker import PDFSignatureWorker


class PDFSignatureController:
    def __init__(self, main_view, viewer_controller):
        self.main_view = main_view
        self.viewer_controller = viewer_controller
        self.service = PDFSignatureService()
        self.document_service = None
        self._signature_worker = None
        self._validation_worker = None
        self._connect_viewer()

    def set_document_service(self, service):
        self.document_service = service

    def request_signature(self):
        if self._signature_worker is not None:
            QMessageBox.warning(self.viewer_controller.view, "Assinatura", "Já existe uma assinatura em andamento.")
            return
        if self.viewer_controller._path is None or self.viewer_controller._info is None:
            return
        dialog = PDFSignatureDialog(
            self.viewer_controller._path,
            self.viewer_controller._info.page_count,
            self.viewer_controller._page,
            self.viewer_controller.view.preview._pixmap_original,
            (
                self.viewer_controller._info.page_width,
                self.viewer_controller._info.page_height,
            ),
            self.viewer_controller.view,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.clear_secret(); return
        request = dialog.build_request()
        dialog.clear_secret()
        worker = PDFSignatureWorker(self.service, request)
        self._signature_worker = worker
        worker.progress.connect(lambda value, message: self.main_view.progress.update(value, message))
        worker.succeeded.connect(self._on_signed)
        worker.failed.connect(self._on_signature_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup_signature(worker))
        worker.finished.connect(worker.deleteLater)
        self.main_view.progress.start("Assinando PDF")
        worker.start()

    def request_validation(self):
        if self._validation_worker is not None or self.viewer_controller._path is None:
            return
        worker = PDFSignatureValidationWorker(self.service, self.viewer_controller._path)
        self._validation_worker = worker
        worker.progress.connect(lambda value, message: self.main_view.progress.update(value, message))
        worker.succeeded.connect(self._on_validated)
        worker.failed.connect(self._on_validation_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup_validation(worker))
        worker.finished.connect(worker.deleteLater)
        self.main_view.progress.start("Validando assinaturas")
        worker.start()

    def _connect_viewer(self):
        view = self.viewer_controller.view
        view.sign_requested.connect(self.request_signature)
        view.validate_signatures_requested.connect(self.request_validation)
        view.btn_sign.setEnabled(False)
        view.btn_validate.setEnabled(False)

    def _on_signed(self, result):
        self.main_view.progress.finish("PDF assinado")
        self.viewer_controller.open_document(str(result.output_path))
        answer = QMessageBox.question(
            self.viewer_controller.view,
            "PDF assinado",
            "Assinatura concluída. Deseja importar o novo PDF para o Mini GED?",
        )
        if answer == QMessageBox.StandardButton.Yes and self.document_service:
            try:
                document = self.document_service.import_document(
                    str(result.output_path), source_type="DIGITAL_SIGNATURE"
                )
                self.document_service.history_service.record_action(
                    document.id, "SIGNED", f"Documento assinado importado: {document.name}"
                )
            except Exception as exc:
                QMessageBox.warning(self.viewer_controller.view, "Mini GED", str(exc))

    def _on_validated(self, results):
        self.main_view.progress.finish("Validação concluída")
        if not results:
            QMessageBox.information(self.viewer_controller.view, "Assinaturas", "O PDF não possui assinaturas digitais.")
            return
        states = ", ".join(result.state for result in results)
        self.viewer_controller.view.signature_label.setText(
            f"{len(results)} assinatura(s) detectada(s): {states}"
        )
        PDFSignatureValidationDialog(results, self.viewer_controller.view).exec()

    def _on_signature_failed(self, message):
        self.main_view.progress.finish("Falha na assinatura")
        QMessageBox.critical(self.viewer_controller.view, "Assinatura", message)

    def _on_validation_failed(self, message):
        self.main_view.progress.finish("Falha na validação")
        QMessageBox.critical(self.viewer_controller.view, "Validação", message)

    def _cleanup_signature(self, worker):
        if self._signature_worker is worker:
            self._signature_worker = None

    def _cleanup_validation(self, worker):
        if self._validation_worker is worker:
            self._validation_worker = None
