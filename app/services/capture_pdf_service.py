from __future__ import annotations

from pathlib import Path
from typing import Callable

import fitz
from PIL import Image, UnidentifiedImageError
from PyQt6.QtGui import QImage
from pypdf import PdfReader, PdfWriter

from app.models.capture_pdf_workspace import CapturePdfPage
from app.utils.atomic_output import atomic_output


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
        return CapturePdfPage(source_kind="SCAN", image=image.convert("RGB"),
            scan_dpi=image.info.get("effective_dpi") or image.info.get("requested_dpi"),
            measurement_source="DEVICE_GEOMETRY" if image.info.get("physical_area_mm") else "SCANNER_DPI" if image.info.get("effective_dpi") else "ESTIMATED" if image.info.get("requested_dpi") else "UNKNOWN",
            physical_area_mm=image.info.get("physical_area_mm"))

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
            image.thumbnail((1400, 1400))
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
        output = Path(output).expanduser().absolute()
        if output.suffix.lower() != ".pdf":
            raise ValueError("O arquivo de saída deve possuir extensão PDF.")
        output.parent.mkdir(parents=True, exist_ok=True)
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
                            PdfReader(cls._image_pdf(image, page))
                        )
                    finally:
                        image.close()
            with atomic_output(output) as temporary:
                with temporary.open("wb") as handle:
                    writer.write(handle)
            return output
        finally:
            writer.close()

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
    def _image_pdf(image: Image.Image, page=None):
        from io import BytesIO

        buffer = BytesIO()
        from reportlab.pdfgen.canvas import Canvas
        from reportlab.lib.utils import ImageReader
        from reportlab.lib.units import mm
        width, height = 210*mm, 297*mm
        geometry = getattr(page, "geometry", None)
        if getattr(page, "output_format", "A4_AUTO") == "DETECTED" and geometry and geometry.reliable_measurement and CapturePdfService.can_crop(page):
            width, height = geometry.physical_width_mm*mm, geometry.physical_height_mm*mm
            if page.rotation in (90,270): width,height = height,width
        canvas = Canvas(buffer, pagesize=(width,height))
        margin = 0 if page is not None and CapturePdfService.can_crop(page) else min(8*mm, width*.04, height*.04)
        scale = min((width-2*margin)/image.width,(height-2*margin)/image.height)
        iw,ih = image.width*scale,image.height*scale
        canvas.drawImage(ImageReader(image),(width-iw)/2,(height-ih)/2,iw,ih)
        canvas.showPage(); canvas.save()
        buffer.seek(0)
        return buffer

    @staticmethod
    def can_crop(page: CapturePdfPage) -> bool:
        geometry = page.geometry
        return bool(geometry and geometry.confidence >= .8
                    and geometry.detection_status in {"DETECTED", "MANUAL"}
                    and (not geometry.possible_clipping or geometry.detection_status == "MANUAL"))

    @staticmethod
    def source_image(page: CapturePdfPage) -> Image.Image:
        if page.image is not None:
            return page.image.copy().convert("RGB")
        if page.source_path is not None:
            with Image.open(page.source_path) as image:
                return image.convert("RGB")
        raise ValueError("Página de imagem sem origem válida.")

    @classmethod
    def _page_image(cls, page: CapturePdfPage) -> Image.Image:
        image = cls.source_image(page)
        if cls.can_crop(page):
            from app.services.document_geometry_service import DocumentGeometryService
            geometry = page.geometry
            try:
                transformed = DocumentGeometryService.transform(image, geometry)
            except Exception as exc:
                image.close()
                raise ValueError("Não foi possível aplicar o recorte. Revise as bordas ou use Redefinir antes de salvar.") from exc
            image.close()
            return transformed
        return image

    @staticmethod
    def _valid_file(path: Path, extensions: set[str]) -> Path:
        source = Path(path).expanduser().resolve(strict=True)
        if not source.is_file() or source.suffix.lower() not in extensions:
            raise ValueError("Tipo de arquivo não suportado.")
        return source
