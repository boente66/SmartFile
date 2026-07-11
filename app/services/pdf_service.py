# app/services/pdf_service.py

from pathlib import Path
from pdf2image import convert_from_path
from pdf2docx import Converter

from app.models.convert_job import ConvertJob


class PDFService:
    """
    Serviço responsável por conversões envolvendo PDF.
    """

    # -------------------------
    # PDF → JPG
    # -------------------------
    @staticmethod
    def convert_pdf_to_jpg(job: ConvertJob, progress=None):

        images = convert_from_path(job.input_path)

        output_dir = Path(job.output_path)

        # Se o usuário passou um arquivo, usamos a pasta
        if output_dir.suffix:
            output_dir = output_dir.parent

        output_dir.mkdir(parents=True, exist_ok=True)

        total = len(images)

        for i, image in enumerate(images):

            output_file = output_dir / f"page_{i + 1}.jpg"

            image.save(output_file, "JPEG")

            if progress:
                value = 20 + int(((i + 1) / total) * 70)
                progress(value, f"Convertendo página {i+1}/{total}")

    # -------------------------
    # PDF → DOCX
    # -------------------------
    @staticmethod
    def convert_pdf_to_docx(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Abrindo PDF")

        converter = Converter(str(job.input_path))

        if progress:
            progress(40, "Convertendo páginas")

        converter.convert(str(job.output_path))

        if progress:
            progress(90, "Finalizando")

        converter.close()

        if progress:
            progress(90, "PDF convertido para DOCX")
