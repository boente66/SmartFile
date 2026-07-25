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
        if not images:
            raise ValueError("O PDF não possui páginas válidas.")
        output_path = Path(job.output_path)
        outputs = PDFService._jpg_output_paths(output_path, len(images))
        existing = next((path for path in outputs if path.exists()), None)
        if existing:
            raise FileExistsError(f"O arquivo de saída já existe: {existing}")
        try:
            for index, (image, output_file) in enumerate(
                zip(images, outputs), start=1
            ):
                image.save(output_file, "JPEG")
                if progress:
                    value = 20 + int((index / len(images)) * 70)
                    progress(
                        value, f"Convertendo página {index}/{len(images)}"
                    )
        finally:
            for image in images:
                image.close()

    # -------------------------
    # PDF → DOCX
    # -------------------------
    @staticmethod
    def convert_pdf_to_docx(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Abrindo PDF")

        converter = Converter(str(job.input_path))
        try:
            if progress:
                progress(40, "Convertendo páginas")
            converter.convert(str(job.output_path))
            if progress:
                progress(90, "Finalizando")
        finally:
            converter.close()

        if progress:
            progress(90, "PDF convertido para DOCX")

    @staticmethod
    def _jpg_output_paths(output_path: Path, count: int) -> list[Path]:
        if count <= 1:
            return [output_path]
        return [
            output_path if index == 1 else output_path.with_name(
                f"{output_path.stem}_{index}.jpg"
            )
            for index in range(1, count + 1)
        ]
