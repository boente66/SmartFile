from pathlib import Path

import fitz

from app.services.pdf_preview_service import PDFPreviewService


def test_generate_thumbnail_uses_pyqt6_image_format(tmp_path: Path):
    pdf_path = tmp_path / "preview.pdf"
    document = fitz.open()
    page = document.new_page(width=200, height=100)
    page.insert_text((20, 40), "SmartFile")
    document.save(pdf_path)
    document.close()

    images = PDFPreviewService.generate_thumbnails(pdf_path, scale=0.5)

    assert len(images) == 1
    assert not images[0].isNull()
    assert images[0].width() == 100
    assert images[0].height() == 50
