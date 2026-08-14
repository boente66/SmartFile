from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz
from PIL import Image, UnidentifiedImageError
from PyQt6.QtGui import QImage
from pypdf import PdfReader, PdfWriter

from app.models.capture_pdf_workspace import CapturePdfPage


class CapturePdfService:
    """Compõe páginas heterogêneas reutilizando os formatos existentes."""

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

    @classmethod
    def pages_from_pdf(cls, path: Path) -> list[CapturePdfPage]:
        source = cls._valid_file(path, {".pdf"})
        try:
            reader = PdfReader(source)
            if reader.is_encrypted:
                raise ValueError("O PDF está protegido por senha.")
            total = len(reader.pages)
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError("O arquivo PDF está inválido ou corrompido.") from exc
        return [
            CapturePdfPage(
                source_kind="PDF", source_path=source, source_page=index,
            )
            for index in range(total)
        ]

    @classmethod
    def pages_from_images(cls, paths: list[Path]) -> list[CapturePdfPage]:
        pages: list[CapturePdfPage] = []
        try:
            for value in paths:
                source = cls._valid_file(value, cls.IMAGE_EXTENSIONS)
                with Image.open(source) as image:
                    image.load()
                    pages.append(CapturePdfPage(
                        source_kind="IMAGE", source_path=source,
                        image=image.convert("RGB"),
                    ))
            return pages
        except (UnidentifiedImageError, OSError) as exc:
            cls.close_pages(pages)
            raise ValueError("Uma das imagens está inválida ou corrompida.") from exc
        except Exception:
            cls.close_pages(pages)
            raise

    @staticmethod
    def page_from_scan(image: Image.Image) -> CapturePdfPage:
        if image is None:
            raise ValueError("O scanner não retornou uma página válida.")
        return CapturePdfPage(source_kind="SCAN", image=image.convert("RGB"))

    @classmethod
    def render_page(
        cls, page: CapturePdfPage, *, scale: float = 1.0,
    ) -> QImage:
        if page.source_kind == "PDF":
            if page.source_path is None or page.source_page is None:
                raise ValueError("Página PDF sem origem válida.")
            document = fitz.open(page.source_path)
            try:
                source = document[page.source_page]
                pixmap = source.get_pixmap(
                    matrix=fitz.Matrix(scale, scale).prerotate(page.rotation),
                    alpha=False,
                )
                return QImage(
                    pixmap.samples, pixmap.width, pixmap.height, pixmap.stride,
                    QImage.Format.Format_RGB888,
                ).copy()
            finally:
                document.close()

        image = cls._page_image(page)
        try:
            if page.rotation:
                image = image.rotate(-page.rotation, expand=True)
            data = image.tobytes("raw", "RGB")
            return QImage(
                data, image.width, image.height, image.width * 3,
                QImage.Format.Format_RGB888,
            ).copy()
        finally:
            image.close()

    @classmethod
    def materialize(
        cls, pages: list[CapturePdfPage], output: Path,
    ) -> Path:
        if not pages:
            raise ValueError("Nenhuma página disponível para gerar o PDF.")
        output = Path(output).expanduser().resolve()
        if output.suffix.lower() != ".pdf":
            raise ValueError("O arquivo de saída deve possuir extensão PDF.")
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f".{output.name}.part")
        temporary.unlink(missing_ok=True)
        writer = PdfWriter()
        try:
            for page in pages:
                if page.source_kind == "PDF":
                    if page.source_path is None or page.source_page is None:
                        raise ValueError("Página PDF sem origem válida.")
                    reader = PdfReader(page.source_path)
                    source_page = reader.pages[page.source_page]
                    if page.rotation:
                        source_page.rotate(page.rotation)
                    writer.add_page(source_page)
                else:
                    image = cls._page_image(page)
                    try:
                        if page.rotation:
                            image = image.rotate(-page.rotation, expand=True)
                        writer.append_pages_from_reader(
                            PdfReader(cls._image_pdf(image))
                        )
                    finally:
                        image.close()
            with temporary.open("wb") as handle:
                writer.write(handle)
            temporary.replace(output)
            return output
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @classmethod
    def render_pages(
        cls,
        pages: list[CapturePdfPage],
        *,
        scale: float = 0.35,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[QImage]:
        rendered: list[QImage] = []
        for page in pages:
            if cancelled and cancelled():
                raise InterruptedError("Renderização cancelada.")
            rendered.append(cls.render_page(page, scale=scale))
        return rendered

    @classmethod
    def close_pages(cls, pages: list[CapturePdfPage]) -> None:
        for page in pages:
            image = page.image
            if image is not None and hasattr(image, "close"):
                image.close()
                page.image = None

    @staticmethod
    def _image_pdf(image: Image.Image):
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PDF")
        buffer.seek(0)
        return buffer

    @staticmethod
    def _page_image(page: CapturePdfPage) -> Image.Image:
        if page.image is not None:
            return page.image.copy().convert("RGB")
        if page.source_path is not None:
            with Image.open(page.source_path) as image:
                return image.convert("RGB")
        raise ValueError("Página de imagem sem origem válida.")

    @staticmethod
    def _valid_file(path: Path, extensions: set[str]) -> Path:
        source = Path(path).expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in extensions:
            raise ValueError("Tipo de arquivo não suportado.")
        return source
