from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from threading import RLock

import fitz
from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from app.errors.pdf_viewer_exceptions import (
    InvalidPDFError,
    PDFInvalidPasswordError,
    PDFPasswordRequiredError,
)
from app.models.pdf_document_info import PDFDocumentInfo
from app.models.pdf_render_request import PDFRenderRequest


class PDFViewerService:
    """Leitura, renderização e pesquisa; nunca altera o PDF."""

    def __init__(self, cache_size: int = 8) -> None:
        self._cache_size = max(2, cache_size)
        self._cache: OrderedDict[tuple, QImage] = OrderedDict()
        self._lock = RLock()

    def document_info(self, path: str | Path, password: str | None = None) -> PDFDocumentInfo:
        pdf_path = self._validated_path(path)
        with self._open(pdf_path, password) as document:
            if document.page_count < 1:
                raise InvalidPDFError("O PDF não possui páginas.")
            metadata = document.metadata or {}
            first = document.load_page(0).rect
            return PDFDocumentInfo(
                path=pdf_path,
                name=pdf_path.name,
                size=pdf_path.stat().st_size,
                page_count=document.page_count,
                page_width=float(first.width),
                page_height=float(first.height),
                title=metadata.get("title") or "",
                author=metadata.get("author") or "",
                subject=metadata.get("subject") or "",
                keywords=metadata.get("keywords") or "",
                creator=metadata.get("creator") or "",
                producer=metadata.get("producer") or "",
                creation_date=metadata.get("creationDate") or "",
                modification_date=metadata.get("modDate") or "",
                password_protected=bool(document.needs_pass),
                signature_count=self._signature_count(document),
            )

    def render_page(self, request: PDFRenderRequest) -> QImage:
        request.validate()
        key = (
            str(request.path.resolve()), request.page_number, round(request.zoom, 3),
            request.rotation % 360, request.highlights,
        )
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached.copy()

        with self._open(self._validated_path(request.path), request.password) as document:
            if request.page_number > document.page_count:
                raise InvalidPDFError("Página fora dos limites do documento.")
            page = document.load_page(request.page_number - 1)
            matrix = fitz.Matrix(request.zoom, request.zoom).prerotate(request.rotation)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            image = QImage(
                pixmap.samples,
                pixmap.width,
                pixmap.height,
                pixmap.stride,
                QImage.Format.Format_RGB888,
            ).copy()
            if request.highlights:
                painter = QPainter(image)
                painter.setPen(QtPenColor)
                painter.setBrush(QColor(255, 215, 0, 90))
                for coords in request.highlights:
                    rect = fitz.Rect(*coords) * matrix
                    painter.drawRect(QRectF(rect.x0, rect.y0, rect.width, rect.height))
                painter.end()

        with self._lock:
            self._cache[key] = image.copy()
            self._cache.move_to_end(key)
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return image

    def render_thumbnail(
        self,
        path: Path,
        page_number: int,
        password: str | None = None,
    ) -> QImage:
        return self.render_page(
            PDFRenderRequest(path=path, page_number=page_number, zoom=0.25, password=password)
        )

    def search(
        self,
        path: Path,
        term: str,
        password: str | None = None,
    ) -> list[tuple[int, tuple[tuple[float, float, float, float], ...]]]:
        query = term.strip()
        if not query:
            return []
        results = []
        with self._open(self._validated_path(path), password) as document:
            for index in range(document.page_count):
                rectangles = document.load_page(index).search_for(query)
                if rectangles:
                    results.append(
                        (index + 1, tuple((r.x0, r.y0, r.x1, r.y1) for r in rectangles))
                    )
        return results

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    @staticmethod
    def _validated_path(path: str | Path) -> Path:
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise InvalidPDFError("O arquivo PDF não foi encontrado.") from exc
        if not resolved.is_file() or resolved.suffix.lower() != ".pdf":
            raise InvalidPDFError("Selecione um arquivo PDF válido.")
        return resolved

    @staticmethod
    def _open(path: Path, password: str | None):
        try:
            document = fitz.open(path)
        except Exception as exc:
            raise InvalidPDFError("O arquivo está corrompido ou não é um PDF válido.") from exc
        if document.needs_pass:
            if password is None:
                document.close()
                raise PDFPasswordRequiredError("Este PDF é protegido por senha.")
            if not document.authenticate(password):
                document.close()
                raise PDFInvalidPasswordError("Senha do PDF incorreta.")
        return document

    @staticmethod
    def _signature_count(document: fitz.Document) -> int:
        count = 0
        for page in document:
            widgets = page.widgets()
            if widgets:
                count += sum(
                    1 for widget in widgets
                    if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE
                )
        return count


QtPenColor = QColor(184, 134, 11, 180)
