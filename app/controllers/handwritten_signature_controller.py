from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QMessageBox
from PyQt6.QtGui import QPixmap

from app.models.pdf_render_request import PDFRenderRequest
from app.services.handwritten_signature_service import HandwrittenSignatureService
from app.views.handwritten_signature_dialog import HandwrittenSignatureDialog
from app.workers.handwritten_signature_worker import HandwrittenSignatureWorker


class HandwrittenSignatureController:
    def __init__(self, main_view, viewer_controller):
        self.main_view = main_view
        self.viewer_controller = viewer_controller
        self.service = HandwrittenSignatureService()
        self.document_service = None
        self._worker: HandwrittenSignatureWorker | None = None
        self.viewer_controller.view.handwritten_sign_requested.connect(self.request_signature)

    def set_document_service(self, service) -> None:
        self.document_service = service

    def request_signature(self) -> None:
        if self._worker is not None:
            QMessageBox.warning(self.viewer_controller.view, "Assinatura manuscrita", "Já existe uma operação em andamento.")
            return
        path = self.viewer_controller._path
        info = self.viewer_controller._info
        if path is None or info is None:
            return
        has_digital = self.service.has_digital_signatures(path)
        confirmed = False
        if has_digital:
            answer = QMessageBox.warning(
                self.viewer_controller.view,
                "PDF já assinado digitalmente",
                "Este PDF possui assinatura criptográfica. Inserir uma marca manuscrita modifica o conteúdo e pode invalidar a assinatura existente.\n\nRecomendação: aplique primeiro a assinatura manuscrita e assine digitalmente por último. Deseja continuar em uma nova cópia?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            confirmed = True
        dialog = HandwrittenSignatureDialog(
            path, info.page_count, self.viewer_controller._page,
            self.viewer_controller.view.preview._pixmap_original,
            (info.page_width, info.page_height), self.viewer_controller._rotation,
            confirmed, self._page_preview, self.viewer_controller.view,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            dialog.clear_signature()
            return
        request = dialog.build_request()
        dialog.clear_signature()
        worker = HandwrittenSignatureWorker(self.service, request)
        self._worker = worker
        worker.progress.connect(lambda value, message: self.main_view.progress.update(value, message))
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup(worker))
        worker.finished.connect(worker.deleteLater)
        self.main_view.progress.start("Aplicando assinatura manuscrita")
        worker.start()

    def _page_preview(self, page_number: int):
        path = self.viewer_controller._path
        if path is None:
            raise ValueError("Nenhum PDF está aberto.")
        request = PDFRenderRequest(
            path=path,
            page_number=page_number,
            zoom=1.0,
            rotation=self.viewer_controller._rotation,
            password=self.viewer_controller._password,
        )
        image = self.viewer_controller.service.render_page(request)
        size = self.service.page_size(path, page_number)
        return QPixmap.fromImage(image), size

    def _on_succeeded(self, result) -> None:
        self.main_view.progress.finish("PDF com assinatura manuscrita salvo")
        self.viewer_controller.open_document(str(result.output_path))
        answer = QMessageBox.question(
            self.viewer_controller.view,
            "Assinatura manuscrita",
            "O novo PDF foi salvo. Deseja importá-lo para o Mini GED?",
        )
        if answer == QMessageBox.StandardButton.Yes and self.document_service:
            try:
                document = self.document_service.import_document(
                    str(result.output_path), source_type="HANDWRITTEN_SIGNATURE"
                )
                name = result.signer_name or "não informado"
                self.document_service.history_service.record_action(
                    document.id,
                    "HANDWRITTEN_SIGNED",
                    f"Assinatura manuscrita eletrônica aplicada por: {name}",
                )
            except Exception as exc:
                QMessageBox.warning(self.viewer_controller.view, "Mini GED", str(exc))

    def _on_failed(self, message: str) -> None:
        self.main_view.progress.finish("Falha na assinatura manuscrita")
        QMessageBox.critical(self.viewer_controller.view, "Assinatura manuscrita", message)

    def _cleanup(self, worker) -> None:
        if self._worker is worker:
            self._worker = None
