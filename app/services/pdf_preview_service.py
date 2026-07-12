# app/services/pdf_preview_service.py

from pathlib import Path
import fitz  # PyMuPDF
from PyQt6.QtGui import QImage


class PDFPreviewService:
    """
    Serviço responsável por gerar thumbnails de páginas PDF.
    """

    @staticmethod
    def generate_thumbnails(
        pdf_path: Path,
        pages: list[int] | None = None,
        scale: float = 0.3
    ) -> list[QImage]:

        images = []

        doc = fitz.open(pdf_path)

        try:

            total_pages = len(doc)

            if pages is None:
                pages = list(range(total_pages))

            for index in pages:

                if index < 0 or index >= total_pages:
                    continue

                page = doc[index]

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(scale, scale)
                )

                img = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format.Format_RGB888
                ).copy()  # copia memória

                images.append(img)

        finally:
            doc.close()

        return images
