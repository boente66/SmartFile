from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox

from app.models.pdf_viewer_context import PDFViewerContext
from app.services.document_validation_service import DocumentValidationService
from app.views.document_validation_dialog import DocumentValidationDialog
from app.workers.document_validation_worker import DocumentValidationWorker


class DocumentValidationController:
    def __init__(self, viewer_controller, database, context=None):
        self.viewer = viewer_controller
        self.context = context
        self.service = DocumentValidationService(database, context)
        self.dialog = None
        self._file = None
        self._result = None
        self._generation = 0
        self._workers = set()
        self.viewer.view.document_validation_requested.connect(self.show)

    def _has(self, permission):
        return self.context is None or self.context.has_permission(permission)

    def show(self):
        organization_id = self.service.active_organization_id()
        try:
            self.service._require(organization_id, "validation.view")
        except Exception as exc:
            QMessageBox.warning(self.viewer.view, "Validação", str(exc)); return
        if self.dialog:
            self.dialog.raise_(); self.dialog.activateWindow(); return
        dialog = DocumentValidationDialog(self.viewer.view)
        self.dialog = dialog; self._file = self.viewer._path; self._result = None
        dialog.config.setVisible(self._has("validation.configure"))
        dialog.file_label.setText(self._file.name if self._file else "Nenhum arquivo selecionado")
        dialog.check_requested.connect(self.check)
        dialog.matching_record_selected.connect(self.select_matching_record)
        dialog.select_file_requested.connect(self.select_file)
        dialog.read_qr_requested.connect(self.read_qr)
        dialog.input_changed.connect(self.invalidate)
        dialog.open_original_requested.connect(self.open_original)
        dialog.export_requested.connect(self.export)
        dialog.revoke_requested.connect(self.revoke)
        dialog.configure_requested.connect(self.configure)
        dialog.finished.connect(self.close)
        dialog.show()

    def invalidate(self):
        self._generation += 1; self._result = None
        for worker in self._workers:
            worker.requestInterruption()
        if self.dialog:
            self.dialog.clear_result(); self.dialog.check.setEnabled(True)

    def close(self, *_):
        self.invalidate()
        dialog = self.dialog; self.dialog = None
        if dialog:
            dialog.deleteLater()

    def organization_changed(self, *_):
        self.close()
        if self.viewer._context.kind == "VALIDATION_ORIGINAL":
            self.viewer.close_document()

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self.dialog, "Arquivo recebido", "", "Arquivos (*)")
        if path:
            self.invalidate(); self._file = Path(path)
            self.dialog.file_label.setText(self._file.name)

    def _start(self, operation, callback):
        self._generation += 1
        generation = self._generation
        organization_id = self.service.active_organization_id()
        dialog = self.dialog
        for previous in self._workers:
            previous.requestInterruption()
        worker = DocumentValidationWorker(operation, audit_actor=self.service.audit.capture(organization_id))
        self._workers.add(worker)
        def current():
            return (self.dialog is dialog and generation == self._generation
                    and organization_id == self.service.active_organization_id())
        def succeeded(result):
            if current():
                dialog.check.setEnabled(True); callback(result)
        def failed(message):
            if current():
                dialog.check.setEnabled(True)
                dialog.result.setPlainText(message)
        worker.succeeded.connect(succeeded); worker.failed.connect(failed)
        worker.finished.connect(lambda: self._workers.discard(worker))
        worker.finished.connect(worker.deleteLater)
        dialog.check.setEnabled(False); worker.start()

    def check(self):
        if not self.dialog:
            return
        self._result = None; self.dialog.clear_result()
        locator = self.dialog.locator.text().strip(); file_path = self._file
        if not locator and not file_path:
            self.dialog.result.setPlainText("Informe um código/QR ou selecione um arquivo."); return
        organization_id = self.service.active_organization_id()
        self._start(lambda cancelled: self.service.validate(organization_id, locator, file_path, cancelled=cancelled), self._display)

    def select_matching_record(self, index):
        if self._result and 0 <= index < len(self._result.matching_records):
            record = self._result.matching_records[index]
            self.dialog.locator.setText(record.human_code)
            self.check()

    def _display(self, result):
        self._result = result
        self.dialog.display(result, can_export=self._has("validation.export"), can_revoke=self._has("validation.revoke"))

    def open_original(self):
        result = self._result
        if not result or not result.record:
            return
        record = result.record
        def opened(path):
            context = PDFViewerContext(kind="VALIDATION_ORIGINAL", title=record.logical_name_snapshot,
                                       protocol_number=record.protocol_snapshot)
            self.viewer.open_document(str(path), context)
        self._start(lambda _: self.service.open_original(record.organization_id, record.id), opened)

    def export(self):
        result = self._result
        if not result or not result.record:
            return
        record = result.record
        path, _ = QFileDialog.getSaveFileName(self.dialog, "Baixar original registrado", record.logical_name_snapshot, "PDF (*.pdf)")
        if path:
            self._start(lambda _: self.service.export_original(record.organization_id, record.id, path),
                        lambda _: self.dialog.result.append("Original exportado; SHA-256 confirmado."))

    def revoke(self):
        if not self._result or not self._result.record:
            return
        record = self._result.record
        reason, accepted = QInputDialog.getText(self.dialog, "Revogação", "Motivo da revogação:")
        if accepted:
            try:
                self.service.revoke(record.organization_id, record.id, reason)
                self.check()
            except Exception as exc:
                QMessageBox.warning(self.dialog, "Revogação", str(exc))

    def configure(self):
        organization_id = self.service.active_organization_id()
        try:
            value = self.service.base_url(organization_id) or ""
            base, accepted = QInputDialog.getText(self.dialog, "Validação web futura",
                "Base HTTPS opcional. Vazio mantém modo local. Não publica documentos nem cria serviço web.",
                QLineEdit.EchoMode.Normal, value)
            if accepted:
                self.service.configure(organization_id, base)
        except Exception as exc:
            QMessageBox.warning(self.dialog, "Configuração", str(exc))

    def read_qr(self):
        path, _ = QFileDialog.getOpenFileName(self.dialog, "Imagem do QR", "", "Imagem (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        def decode(cancelled):
            import cv2
            import numpy as np
            from PIL import Image
            with Image.open(path) as image:
                image.thumbnail((2400, 2400))
                pixels = np.asarray(image.convert("RGB"))
            if cancelled():
                raise InterruptedError()
            value, _, _ = cv2.QRCodeDetector().detectAndDecode(pixels)
            if not value:
                raise ValueError("QR não legível. Informe o código ou token manualmente.")
            from app.services.validation_locator_service import ValidationLocatorService
            ValidationLocatorService.parse(value)
            return value
        self._start(decode, lambda value: self.dialog.locator.setText(value))
