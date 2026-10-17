from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSlot
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QMessageBox

from app.services.qr_reposition_service import QrRepositionService
from app.utils.file_naming import safe_output_path
from app.views.pdf_signature_dialog import PDFSignatureDialog
from app.views.qr_reposition_dialog import QrRepositionDialog, configure_reposition
from app.workers.document_validation_worker import DocumentValidationWorker


class QrRepositionController(QObject):
    def __init__(self, signature_controller):
        super().__init__(signature_controller.viewer_controller.view)
        self.signatures = signature_controller
        self.viewer = signature_controller.viewer_controller
        self._workers = set()
        self._closing = False
        self.viewer.view.preview.page_double_clicked.connect(self.request)

    def _start(self, operation, kind, source):
        validation = self.signatures.service.validation_service
        worker = DocumentValidationWorker(operation, audit_actor=validation.audit.capture(validation.active_organization_id()))
        worker.setProperty('operationKind', kind)
        worker.source_path = source
        self._workers.add(worker)
        worker.succeeded.connect(self._succeeded)
        worker.failed.connect(self._failed)
        worker.finished.connect(self._finished)
        worker.finished.connect(worker.deleteLater)
        worker.start()

    @pyqtSlot(float, float)
    def request(self, x, y):
        if self._closing or self._workers or self.viewer._path is None:
            return
        if self.viewer._context.kind == 'VALIDATION_ORIGINAL':
            return
        validation = self.signatures.service.validation_service
        if validation is None:
            return
        angle = self.viewer._rotation % 360
        if angle == 90:
            x, y = y, 1-x
        elif angle == 180:
            x, y = 1-x, 1-y
        elif angle == 270:
            x, y = 1-y, x
        source, page_number = self.viewer._path, self.viewer._page
        def inspect(cancelled):
            import fitz
            service = QrRepositionService(validation)
            with fitz.open(source) as document:
                page = document[page_number-1]
                point = (x*page.rect.width, y*page.rect.height)
            location = service.inspect(source, page_number, point)
            with fitz.open(source) as document:
                service.remove(document, location, remove_signatures=location.digitally_signed)
                preview = document[page_number-1].get_pixmap(matrix=fitz.Matrix(1,1)).tobytes('png')
            return location, preview
        self._start(inspect, 'inspect', source)

    def _current(self, worker):
        return (not self._closing and self.viewer._path == worker.source_path
                and self.signatures._signature_scope_current(worker.audit_actor))

    @pyqtSlot(object)
    def _succeeded(self, result):
        worker = self.sender()
        if not self._current(worker):
            return
        if worker.property('operationKind') != 'inspect':
            self.viewer.open_document(str(result.output_path))
            return
        location, png = result
        pixmap = QPixmap(); pixmap.loadFromData(png)
        source = worker.source_path
        output_dir = Path.home() / 'Documents'
        if not output_dir.is_dir():
            output_dir = Path.home()
        output = safe_output_path(output_dir / f'{source.stem}_qr_reposicionado.pdf')
        if location.digitally_signed:
            answer = QMessageBox.question(self.viewer.view, 'Nova assinatura A1 necessária',
                'A cópia corrigida removerá as assinaturas A1 anteriores e será assinada novamente com o certificado escolhido. O original será preservado. Continuar?')
            if answer != QMessageBox.StandardButton.Yes:
                return
            dialog = PDFSignatureDialog(source, self.viewer._info.page_count, location.page_number,
                                        pixmap, location.page_size, self.viewer.view)
            configure_reposition(dialog.qr_options, location)
            dialog.qr_overlay.unlock()
            dialog.output_edit.setText(str(output))
            dialog.placement.setToolTip('Dê duplo clique no QR e arraste. Defina uma nova assinatura A1.')
            if dialog.exec() != QDialog.DialogCode.Accepted:
                dialog.clear_secret(); return
            request = dialog.build_request(); dialog.clear_secret()
            request.replace_qr = True
            request.validation_document_id = location.record.document_id
            self._start(lambda cancelled: self.signatures.service.sign(request), 'save', source)
        else:
            dialog = QrRepositionDialog(pixmap, location, output, self.viewer.view)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            rect = dialog.options.values()['qr_rect']
            destination = Path(dialog.output.text())
            self._start(lambda cancelled: QrRepositionService(self.signatures.service.validation_service).move(
                source, destination, location.page_number, rect), 'save', source)

    @pyqtSlot(str)
    def _failed(self, message):
        if self.sender().property('operationKind') == 'inspect' and message.startswith('Não foi encontrado neste ponto'):
            return
        if self._current(self.sender()):
            QMessageBox.information(self.viewer.view, 'Reposicionar QR', message)

    @pyqtSlot()
    def _finished(self):
        self._workers.discard(self.sender())

    def shutdown(self):
        self._closing = True
        for worker in list(self._workers):
            worker.requestInterruption()
            worker.wait()
