# app/services/doc_service.py

from pathlib import Path
from docx2pdf import convert
from pdf2image import convert_from_path

from app.models.convert_job import ConvertJob


class DOCService:
    """
    Serviço responsável por conversões envolvendo DOCX.
    """

    # -------------------------
    # DOCX → PDF
    # -------------------------
    @staticmethod
    def convert_docx_to_pdf(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Convertendo documento para PDF")

        convert(str(job.input_path), str(job.output_path))

        if progress:
            progress(90, "DOCX convertido para PDF")

    # -------------------------
    # DOCX → JPG
    # -------------------------
    @staticmethod
    def convert_docx_to_jpg(job: ConvertJob, progress=None):

        temp_pdf = job.output_path.with_suffix(".pdf")

        try:

            if progress:
                progress(10, "Convertendo DOCX para PDF")

            convert(str(job.input_path), str(temp_pdf))

            if progress:
                progress(40, "Gerando imagens")

            images = convert_from_path(temp_pdf)

            output_dir = job.output_path.parent
            output_dir.mkdir(parents=True, exist_ok=True)

            total = len(images)

            for i, image in enumerate(images):

                output_file = output_dir / f"page_{i + 1}.jpg"
                image.save(output_file, "JPEG")

                if progress:
                    value = 40 + int(((i + 1) / total) * 50)
                    progress(value, f"Convertendo página {i+1}/{total}")

        finally:
            # Remove PDF temporário
            if temp_pdf.exists():
                temp_pdf.unlink()
