from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter, QPixmap
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from app.errors.pdf_viewer_exceptions import PDFPasswordRequiredError
from app.models.pdf_document_info import PDFDocumentInfo
from app.models.pdf_render_request import PDFRenderRequest
from app.services.pdf_viewer_service import PDFViewerService
from app.views.pdf_viewer_view import PDFViewerView
from app.workers.pdf_render_worker import PDFRenderWorker
from app.workers.pdf_search_worker import PDFSearchWorker
from app.workers.pdf_thumbnail_worker import PDFThumbnailWorker


class PDFViewerController:
    MIN_ZOOM = 0.5
    MAX_ZOOM = 2.0

    def __init__(self, workspace):
        self.workspace = workspace
        self.view = PDFViewerView()
        self.service = PDFViewerService()
        self._path: Path | None = None
        self._password: str | None = None
        self._info: PDFDocumentInfo | None = None
        self._page = 1
        self._zoom = 1.0
        self._rotation = 0
        self._render_worker: PDFRenderWorker | None = None
        self._background_workers: set[PDFRenderWorker] = set()
        self._workers: set[object] = set()
        self._thumbnail_worker: PDFThumbnailWorker | None = None
        self._search_worker: PDFSearchWorker | None = None
        self._search_results: list[tuple[int, tuple]] = []
        self._search_index = -1
        self._fullscreen = False
        self._connect_signals()
        self.workspace.register_view("pdf_viewer", self.view)

    def activate(self):
        self.workspace.show_view("pdf_viewer")

    def open_document(self, path: str):
        self.close_document()
        try:
            info = self.service.document_info(path)
        except PDFPasswordRequiredError:
            password, accepted = QInputDialog.getText(
                self.view,
                "PDF protegido",
                "Informe a senha do documento:",
                QLineEdit.EchoMode.Password,
            )
            if not accepted:
                return
            try:
                info = self.service.document_info(path, password)
                self._password = password
            except Exception as exc:
                QMessageBox.warning(self.view, "Visualizador de PDF", str(exc))
                return
        except Exception as exc:
            QMessageBox.warning(self.view, "Visualizador de PDF", str(exc))
            return

        self._path = info.path
        self._info = info
        self._page = 1
        self._zoom = 1.0
        self._rotation = 0
        self.view.set_document(info)
        self.activate()
        self._render_current()
        self._start_thumbnails()

    def close_document(self):
        for worker in list(self._workers):
            worker.requestInterruption()
        self._render_worker = None
        self._thumbnail_worker = None
        self._search_worker = None
        self._path = None
        self._password = None
        self._info = None
        self._search_results.clear()
        self._search_index = -1
        self.service.clear_cache()
        self.view.set_document_loaded(False)
        self.view.info_panel.set_info(None)
        self.view.preview.set_pixmap(QPixmap())

    def go_to_page(self, page_number: int):
        if self._info is None:
            return
        bounded = min(max(1, int(page_number)), self._info.page_count)
        if bounded != self._page:
            self._page = bounded
        self._render_current()

    def set_zoom(self, value: float):
        bounded = min(max(float(value), self.MIN_ZOOM), self.MAX_ZOOM)
        if abs(bounded - self._zoom) < 0.001:
            return
        self._zoom = bounded
        self._render_current()

    def _connect_signals(self):
        self.view.back_requested.connect(self.return_to_documents)
        self.view.open_requested.connect(self.open_document)
        self.view.page_requested.connect(self.go_to_page)
        self.view.first_requested.connect(lambda: self.go_to_page(1))
        self.view.previous_requested.connect(lambda: self.go_to_page(self._page - 1))
        self.view.next_requested.connect(lambda: self.go_to_page(self._page + 1))
        self.view.last_requested.connect(lambda: self.go_to_page(self._info.page_count if self._info else 1))
        self.view.zoom_requested.connect(self.set_zoom)
        self.view.fit_width_requested.connect(self._fit_width)
        self.view.fit_page_requested.connect(self._fit_page)
        self.view.rotate_left_requested.connect(lambda: self._rotate(-90))
        self.view.rotate_right_requested.connect(lambda: self._rotate(90))
        self.view.search_requested.connect(self._start_search)
        self.view.search_previous_requested.connect(lambda: self._move_search(-1))
        self.view.search_next_requested.connect(lambda: self._move_search(1))
        self.view.print_requested.connect(self._print_document)
        self.view.fullscreen_requested.connect(self._toggle_fullscreen)
        self.view.escape_requested.connect(self._exit_fullscreen)

    def return_to_documents(self):
        """Fecha o PDF atual e retorna ao módulo oficial de Documentos."""

        self._exit_fullscreen()
        self.close_document()
        self.workspace.show_view("documents")

    def _render_current(self):
        if self._path is None or self._info is None:
            return
        if self._render_worker is not None and self._render_worker.isRunning():
            self._render_worker.requestInterruption()
        highlights = self._current_highlights()
        request = PDFRenderRequest(
            path=self._path,
            page_number=self._page,
            zoom=self._zoom,
            rotation=self._rotation,
            password=self._password,
            highlights=highlights,
        )
        worker = PDFRenderWorker(self.service, request)
        self._workers.add(worker)
        self._render_worker = worker
        self.view.set_loading(True)
        worker.succeeded.connect(
            lambda completed, image, worker=worker: self._on_rendered(worker, completed, image)
        )
        worker.failed.connect(lambda message: QMessageBox.warning(self.view, "Visualizador", message))
        worker.finished.connect(lambda worker=worker: self._cleanup_render(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_rendered(self, worker, request, image: QImage):
        if worker is not self._render_worker or request.page_number != self._page:
            return
        self.view.set_rendered_page(
            self._page, self._info.page_count, QPixmap.fromImage(image), self._zoom
        )
        self._preload_adjacent()

    def _cleanup_render(self, worker):
        self._workers.discard(worker)
        if self._render_worker is worker:
            self._render_worker = None

    def _preload_adjacent(self):
        if self._path is None or self._info is None:
            return
        for page in (self._page - 1, self._page + 1):
            if not 1 <= page <= self._info.page_count:
                continue
            request = PDFRenderRequest(
                path=self._path, page_number=page, zoom=self._zoom,
                rotation=self._rotation, password=self._password,
            )
            worker = PDFRenderWorker(self.service, request)
            self._workers.add(worker)
            self._background_workers.add(worker)
            worker.finished.connect(lambda worker=worker: self._cleanup_background(worker))
            worker.finished.connect(worker.deleteLater)
            worker.start()

    def _cleanup_background(self, worker):
        self._background_workers.discard(worker)
        self._workers.discard(worker)

    def _start_thumbnails(self):
        if self._path is None or self._info is None:
            return
        worker = PDFThumbnailWorker(
            self.service, self._path, self._info.page_count, self._password
        )
        self._thumbnail_worker = worker
        self._workers.add(worker)
        worker.thumbnail_ready.connect(self.view.set_thumbnail)
        worker.failed.connect(lambda message: self.view.set_loading(False, message))
        worker.finished.connect(lambda worker=worker: self._cleanup_thumbnail(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _cleanup_thumbnail(self, worker):
        self._workers.discard(worker)
        if self._thumbnail_worker is worker:
            self._thumbnail_worker = None

    def _start_search(self, term: str):
        if self._path is None:
            return
        if self._search_worker is not None and self._search_worker.isRunning():
            self._search_worker.requestInterruption()
        worker = PDFSearchWorker(self.service, self._path, term, self._password)
        self._search_worker = worker
        self._workers.add(worker)
        self.view.set_loading(True, "Pesquisando…")
        worker.succeeded.connect(
            lambda query, results, worker=worker: self._on_search_results(worker, query, results)
        )
        worker.failed.connect(lambda message: QMessageBox.warning(self.view, "Pesquisa", message))
        worker.finished.connect(lambda worker=worker: self._cleanup_search(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_search_results(self, worker, _term, results):
        if worker is not self._search_worker:
            return
        self._search_results = [
            (page, (rectangle,))
            for page, rectangles in results
            for rectangle in rectangles
        ]
        self._search_index = 0 if self._search_results else -1
        self.view.update_search_count(
            self._search_index + 1 if self._search_index >= 0 else 0,
            len(self._search_results),
        )
        self.view.set_loading(False)
        if self._search_index >= 0:
            self._page = self._search_results[0][0]
            self._render_current()
        else:
            QMessageBox.information(self.view, "Pesquisa", "Nenhuma ocorrência encontrada.")

    def _cleanup_search(self, worker):
        self._workers.discard(worker)
        if self._search_worker is worker:
            self._search_worker = None

    def _move_search(self, direction: int):
        if not self._search_results:
            return
        self._search_index = (self._search_index + direction) % len(self._search_results)
        self.view.update_search_count(self._search_index + 1, len(self._search_results))
        self._page = self._search_results[self._search_index][0]
        self._render_current()

    def _current_highlights(self):
        if 0 <= self._search_index < len(self._search_results):
            page, rectangles = self._search_results[self._search_index]
            if page == self._page:
                return rectangles
        return ()

    def _rotate(self, delta: int):
        self._rotation = (self._rotation + delta) % 360
        self._render_current()

    def _fit_width(self):
        if self._info is None:
            return
        available = self.view.available_preview_size()
        width = self._info.page_height if self._rotation in {90, 270} else self._info.page_width
        self.set_zoom((available.width() - 24) / max(width, 1))

    def _fit_page(self):
        if self._info is None:
            return
        available = self.view.available_preview_size()
        width, height = self._info.page_width, self._info.page_height
        if self._rotation in {90, 270}:
            width, height = height, width
        self.set_zoom(min((available.width() - 24) / width, (available.height() - 24) / height))

    def _print_document(self):
        if self._path is None or self._info is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self.view)
        dialog.setMinMax(1, self._info.page_count)
        dialog.setFromTo(1, self._info.page_count)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        print_range = printer.printRange()
        if print_range == QPrinter.PrintRange.CurrentPage:
            pages = [self._page]
        elif print_range == QPrinter.PrintRange.PageRange:
            start = max(1, printer.fromPage())
            end = min(self._info.page_count, printer.toPage() or self._info.page_count)
            pages = range(start, end + 1)
        else:
            pages = range(1, self._info.page_count + 1)
        painter = QPainter(printer)
        try:
            for index, page in enumerate(pages):
                if index > 0:
                    printer.newPage()
                image = self.service.render_page(
                    PDFRenderRequest(self._path, page, zoom=1.5, password=self._password)
                )
                target = printer.pageRect(QPrinter.Unit.DevicePixel).toRect()
                scaled = image.scaled(
                    target.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                x = target.x() + (target.width() - scaled.width()) // 2
                y = target.y() + (target.height() - scaled.height()) // 2
                painter.drawImage(x, y, scaled)
        finally:
            painter.end()

    def _toggle_fullscreen(self):
        window = self.view.window()
        if self._fullscreen:
            self.view.set_presentation_mode(False)
            window.showNormal()
        else:
            self.view.set_presentation_mode(True)
            window.showFullScreen()
        self._fullscreen = not self._fullscreen

    def _exit_fullscreen(self):
        if self._fullscreen:
            self._toggle_fullscreen()
