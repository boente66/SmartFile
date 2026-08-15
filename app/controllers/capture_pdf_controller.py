from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QMessageBox

from app.models.capture_pdf_workspace import CapturePdfWorkspace
from app.models.scan_config_model import ScanConfigModel
from app.services.capture_pdf_service import CapturePdfService
from app.services.document_service import DocumentService
from app.services.scan_service import ScanService
from app.utils.file_naming import safe_output_path
from app.views.capture_pdf_view import CapturePdfView
from app.views.scanner_import_dialog import ScannerImportDialog
from app.workers.capture_pdf_worker import CapturePdfWorker
from app.workers.scan_worker import ScanWorker

logger = logging.getLogger(__name__)


class CapturePdfController:
    """Coordena Scanner, composição de PDF, preview e importação documental."""

    def __init__(
        self,
        workspace,
        document_service: DocumentService,
        imported_callback=None,
        session_context=None,
    ):
        self.workspace = workspace
        self.document_service = document_service
        self.imported_callback = imported_callback
        self.session_context = session_context
        self.view = CapturePdfView()
        self.state = CapturePdfWorkspace()
        self._devices_loaded = False
        self._scan_worker: ScanWorker | None = None
        self._operation_worker: CapturePdfWorker | None = None
        self._render_worker: CapturePdfWorker | None = None
        self._render_generation = 0
        self._render_pending = False
        self._connect_signals()
        self.workspace.register_view("capture_pdf", self.view)
        self.workspace.register_alias("scanner", "capture_pdf")
        self.workspace.register_alias("pdf", "capture_pdf")

    def _connect_signals(self) -> None:
        self.view.scan_requested.connect(self.on_scan_requested)
        self.view.import_images_requested.connect(self.on_import_images)
        self.view.open_pdf_requested.connect(self.on_open_pdf)
        self.view.add_pdfs_requested.connect(self.on_add_pdfs)
        self.view.remove_requested.connect(self.on_remove_pages)
        self.view.reorder_requested.connect(self.on_reorder_pages)
        self.view.rotate_requested.connect(self.on_rotate_pages)
        self.view.extract_requested.connect(self.on_extract_pages)
        self.view.split_requested.connect(self.on_split_pdf)
        self.view.save_requested.connect(self.on_save_pdf)
        self.view.add_to_ged_requested.connect(self.on_add_to_ged)
        self.view.clear_requested.connect(self.on_clear_requested)
        self.view.refresh_devices_requested.connect(self._load_devices)
        self.view.device_changed.connect(self._load_sources)
        self.view.current_page_changed.connect(self._set_current_page)

    # API pública usada pela navegação e pelo módulo Documentos.
    def activate(self) -> None:
        self.workspace.show_view("capture_pdf")
        if not self._devices_loaded:
            self._load_devices()

    def open_document(self, path: str) -> None:
        self.activate()
        self.on_open_pdf(path)

    def close_document(self) -> None:
        self.clear_workspace(confirm=False)

    def _load_devices(self) -> None:
        devices = ScanService.list_devices()
        self.view.set_devices(devices)
        self._devices_loaded = True

    def _load_sources(self, device_name: str) -> None:
        if not device_name or device_name == "Nenhum scanner encontrado":
            self.view.set_sources([])
            return
        self.view.set_sources(ScanService.list_sources(device_name))

    def on_scan_requested(self) -> None:
        if self._scan_worker is not None or self._operation_worker is not None:
            QMessageBox.information(self.view, "Captura e PDF", "Aguarde a operação atual.")
            return
        values = self.view.get_scan_config()
        try:
            config = ScanConfigModel(
                device_name=values["device"],
                dpi=values["dpi"],
                color_mode=values["color"],
                source_name=values["source"],
            )
            config.validate()
        except Exception as exc:
            QMessageBox.warning(self.view, "Scanner", ScanService.friendly_error(exc, values.get("source")))
            return
        worker = ScanWorker(config)
        self._scan_worker = worker
        worker.progress.connect(self._show_progress)
        worker.succeeded.connect(self._on_scan_succeeded)
        worker.failed.connect(self._on_scan_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup_scan_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self._set_busy(True)
        worker.start()

    def _on_scan_succeeded(self, image) -> None:
        try:
            page = CapturePdfService.page_from_scan(image)
            self.state.add_pages([page])
            self.state.source = "SCANNER"
            if self.state.output_name == "Novo documento":
                self.state.output_name = "Documento digitalizado"
            self._schedule_render()
        finally:
            if hasattr(image, "close"):
                image.close()

    def _on_scan_failed(self, message: str) -> None:
        logger.warning("capture_pdf.scan.failed message=%s", message)
        QMessageBox.critical(self.view, "Erro ao digitalizar", message)

    def _cleanup_scan_worker(self, worker: ScanWorker) -> None:
        if self._scan_worker is worker:
            self._scan_worker = None
            self._set_busy(False)

    def on_import_images(self, paths: list[str]) -> None:
        sources = [Path(path) for path in paths]
        if not sources:
            return

        def task(progress, cancelled):
            progress(10, "Validando imagens")
            if cancelled():
                raise InterruptedError
            result = CapturePdfService.pages_from_images(sources)
            progress(100, "Imagens importadas")
            return result

        self._start_operation(task, self._on_images_loaded, "Importar imagens")

    def _on_images_loaded(self, pages) -> None:
        self.state.add_pages(pages)
        self.state.source = self.state.source or "IMAGES"
        if self.state.output_name == "Novo documento":
            self.state.output_name = sources_name(pages, "Imagens importadas")
        self._schedule_render()

    def on_open_pdf(self, path: str) -> None:
        source = Path(path)

        def task(progress, cancelled):
            progress(10, "Abrindo PDF")
            if cancelled():
                raise InterruptedError
            pages = CapturePdfService.pages_from_pdf(source)
            progress(100, "PDF aberto")
            return pages

        self._start_operation(
            task,
            lambda pages: self._replace_with_pdf(source, pages),
            "Abrir PDF",
        )

    def _replace_with_pdf(self, source: Path, pages) -> None:
        CapturePdfService.close_pages(self.state.clear())
        self.state.add_pages(pages)
        self.state.source = "PDF"
        self.state.output_name = source.stem
        self.state.dirty = False
        self._schedule_render()

    def on_add_pdfs(self, paths: list[str]) -> None:
        sources = [Path(path) for path in paths]
        if not sources:
            return

        def task(progress, cancelled):
            pages = []
            try:
                for index, source in enumerate(sources):
                    if cancelled():
                        raise InterruptedError
                    progress(10 + int(index * 80 / len(sources)), f"Adicionando {source.name}")
                    pages.extend(CapturePdfService.pages_from_pdf(source))
                progress(100, "PDFs adicionados")
                return pages
            except Exception:
                CapturePdfService.close_pages(pages)
                raise

        self._start_operation(task, self._on_pdfs_added, "Adicionar PDFs")

    def _on_pdfs_added(self, pages) -> None:
        self.state.add_pages(pages)
        self.state.source = self.state.source or "PDF"
        if self.state.output_name == "Novo documento":
            self.state.output_name = sources_name(pages, "Documento mesclado")
        self._schedule_render()

    def on_remove_pages(self, indexes: list[int]) -> None:
        if not indexes:
            return
        if len(indexes) == len(self.state.pages):
            answer = QMessageBox.question(
                self.view, "Remover páginas", "Remover todas as páginas do workspace?"
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        CapturePdfService.close_pages(self.state.remove(indexes))
        self._schedule_render()

    def on_reorder_pages(self, page_ids: list[str]) -> None:
        try:
            self.state.reorder(page_ids)
            self._schedule_render()
        except ValueError as exc:
            QMessageBox.warning(self.view, "Reordenar páginas", str(exc))

    def on_rotate_pages(self, indexes: list[int], degrees: int) -> None:
        try:
            self.state.rotate(indexes, degrees)
            self._schedule_render()
        except ValueError as exc:
            QMessageBox.warning(self.view, "Girar páginas", str(exc))

    def on_extract_pages(self, indexes: list[int], path: str) -> None:
        pages = [self.state.pages[index] for index in indexes if 0 <= index < len(self.state.pages)]
        if not pages:
            return
        self._materialize_to(Path(path), pages, "Extrair páginas", reopen=False)

    def on_save_pdf(self, path: str) -> None:
        if not self.state.pages:
            QMessageBox.warning(self.view, "Salvar PDF", "Nenhuma página disponível.")
            return
        self._materialize_to(Path(path), self.state.pages, "Salvar PDF", reopen=True)

    def on_split_pdf(self, directory: str) -> None:
        if not self.state.pages:
            return
        target = Path(directory).expanduser().resolve()
        snapshot = self.state.snapshot()

        def task(progress, cancelled):
            outputs = []
            try:
                target.mkdir(parents=True, exist_ok=True)
                for index, page in enumerate(snapshot, start=1):
                    if cancelled():
                        raise InterruptedError
                    progress(
                        int(index * 100 / len(snapshot)),
                        f"Gerando página {index} de {len(snapshot)}",
                    )
                    output = safe_output_path(
                        target / f"{self.state.output_name}_pagina_{index}.pdf"
                    )
                    outputs.append(CapturePdfService.materialize([page], output))
                return outputs
            finally:
                CapturePdfService.close_pages(snapshot)

        self._start_operation(
            task,
            lambda outputs: QMessageBox.information(
                self.view,
                "Dividir PDF",
                f"{len(outputs)} arquivo(s) criado(s) em:\n{target}",
            ),
            "Dividir PDF",
        )

    def _materialize_to(self, requested: Path, pages, title: str, *, reopen: bool) -> None:
        output = safe_output_path(requested.expanduser())
        snapshot = CapturePdfWorkspace(pages=list(pages)).snapshot()

        def task(progress, cancelled):
            try:
                progress(10, "Preparando páginas")
                if cancelled():
                    raise InterruptedError
                result = CapturePdfService.materialize(snapshot, output)
                progress(100, "PDF gerado")
                return result
            finally:
                CapturePdfService.close_pages(snapshot)

        def succeeded(result: Path) -> None:
            QMessageBox.information(self.view, title, f"PDF salvo com sucesso:\n{result}")
            if reopen:
                self.state.output_name = result.stem
                self.state.dirty = False
                self._update_view_state()

        self._start_operation(task, succeeded, title)

    def on_add_to_ged(self) -> None:
        if not self.state.pages:
            QMessageBox.warning(self.view, "Adicionar ao SmartFile", "Nenhuma página disponível.")
            return
        allowed = None
        if self.session_context and self.session_context.is_authenticated():
            allowed = [item.organization_id for item in self.session_context.memberships]
        dialog = ScannerImportDialog(
            self.document_service,
            self.view,
            allowed_organization_ids=allowed,
        )
        dialog.setWindowTitle("Adicionar documento ao SmartFile")
        dialog.title.setText(self.state.output_name)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        metadata = dialog.values()
        metadata["source_type"] = "SCANNER" if self.state.source == "SCANNER" else "PDF_TOOLS"
        temporary = self.document_service.database.paths.temp / f"capture-pdf-{uuid4()}.pdf"
        snapshot = self.state.snapshot()

        def task(progress, cancelled):
            try:
                progress(10, "Gerando documento final")
                if cancelled():
                    raise InterruptedError
                CapturePdfService.materialize(snapshot, temporary)
                progress(55, "Adicionando ao armazenamento gerenciado")
                if cancelled():
                    raise InterruptedError
                document = self.document_service.import_document(str(temporary), **metadata)
                progress(100, "Documento adicionado ao SmartFile")
                return document
            finally:
                temporary.unlink(missing_ok=True)
                CapturePdfService.close_pages(snapshot)

        self._start_operation(task, self._on_ged_succeeded, "Adicionar ao SmartFile")

    def _on_ged_succeeded(self, document) -> None:
        if self.imported_callback:
            self.imported_callback()
        QMessageBox.information(
            self.view,
            "Adicionar ao SmartFile",
            f"Documento adicionado com sucesso: {document.name}",
        )

    def on_clear_requested(self) -> None:
        self.clear_workspace(confirm=True)

    def clear_workspace(self, *, confirm: bool) -> bool:
        if confirm and self.state.pages:
            answer = QMessageBox.question(
                self.view,
                "Limpar workspace",
                "Descartar todas as páginas desta sessão?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return False
        CapturePdfService.close_pages(self.state.clear())
        self.view.set_pages([], -1)
        self._update_view_state()
        return True

    def _start_operation(self, task, succeeded, title: str) -> None:
        if self._operation_worker is not None:
            QMessageBox.information(self.view, title, "Aguarde a operação atual.")
            return
        worker = CapturePdfWorker(task)
        self._operation_worker = worker
        worker.progress.connect(self._show_progress)
        worker.succeeded.connect(succeeded)
        worker.failed.connect(lambda message: self._operation_failed(title, message))
        worker.finished.connect(lambda worker=worker: self._cleanup_operation(worker))
        worker.finished.connect(worker.deleteLater)
        self._set_busy(True)
        worker.start()

    def _cleanup_operation(self, worker: CapturePdfWorker) -> None:
        if self._operation_worker is worker:
            self._operation_worker = None
            self._set_busy(False)

    def _operation_failed(self, title: str, message: str) -> None:
        logger.warning("capture_pdf.operation.failed title=%s message=%s", title, message)
        QMessageBox.critical(self.view, title, message)

    def _schedule_render(self) -> None:
        self._render_generation += 1
        if self._render_worker is not None:
            self._render_pending = True
            self._render_worker.requestInterruption()
            return
        generation = self._render_generation
        snapshot = self.state.snapshot()

        def task(progress, cancelled):
            try:
                progress(10, "Gerando visualização")
                images = CapturePdfService.render_pages(snapshot, scale=0.55, cancelled=cancelled)
                progress(100, "Visualização pronta")
                return generation, [page.id for page in snapshot], images
            finally:
                CapturePdfService.close_pages(snapshot)

        worker = CapturePdfWorker(task)
        self._render_worker = worker
        worker.succeeded.connect(self._render_succeeded)
        worker.failed.connect(lambda message: self._operation_failed("Visualização", message))
        worker.finished.connect(lambda worker=worker: self._cleanup_render(worker))
        worker.finished.connect(worker.deleteLater)
        self._update_view_state()
        worker.start()

    def _render_succeeded(self, result) -> None:
        generation, page_ids, images = result
        if generation != self._render_generation:
            return
        pixmaps = [(page_id, QPixmap.fromImage(image)) for page_id, image in zip(page_ids, images)]
        self.view.set_pages(pixmaps, self.state.current_page)
        self._update_view_state()

    def _cleanup_render(self, worker: CapturePdfWorker) -> None:
        if self._render_worker is worker:
            self._render_worker = None
            if self._render_pending or self._render_generation:
                pending = self._render_pending
                self._render_pending = False
                if pending:
                    self._schedule_render()

    def _set_current_page(self, index: int) -> None:
        if 0 <= index < len(self.state.pages):
            self.state.current_page = index

    def _set_busy(self, busy: bool) -> None:
        self.view.set_document_state(self.state.output_name, len(self.state.pages), busy)

    def _update_view_state(self) -> None:
        busy = self._operation_worker is not None or self._scan_worker is not None
        self.view.set_document_state(self.state.output_name, len(self.state.pages), busy)

    def _show_progress(self, value: int, message: str) -> None:
        self.view.set_status(f"{message} {value}%")


def sources_name(pages, fallback: str) -> str:
    for page in pages:
        if page.source_path is not None:
            return page.source_path.stem
    return fallback
