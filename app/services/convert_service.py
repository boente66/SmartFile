from app.services.pdf_service import PDFService
from app.services.doc_service import DOCService
from app.services.xlsx_service import XLSXService
from app.services.csv_service import CSVService
from app.services.txt_service import TXTService
from app.services.image_service import ImageService
from app.errors.conversion_exceptions import ConversionCancelledError


class ConvertService:

    SUPPORTED_CONVERSIONS: dict[str, tuple[str, ...]] = {
        "PDF": ("DOCX", "JPG"),
        "DOCX": ("PDF", "JPG"),
        "JPG": ("PDF",),
        "JPEG": ("PDF",),
        "PNG": ("PDF", "JPG"),
        "TIFF": ("PDF", "JPG"),
        "TIF": ("PDF", "JPG"),
        "XLSX": ("CSV",),
        "CSV": ("XLSX",),
        "TXT": ("PDF",),
    }

    @classmethod
    def available_targets(cls, source_format: str) -> tuple[str, ...]:
        """Retorna somente destinos realmente implementados para a origem."""

        source = cls._canonical_format(source_format)
        return cls.SUPPORTED_CONVERSIONS.get(source, ())

    @classmethod
    def supports(cls, source_format: str, target_format: str) -> bool:
        source = cls._canonical_format(source_format)
        target = cls._canonical_format(target_format)
        return target in cls.available_targets(source)

    @staticmethod
    def execute(job, progress_callback=None, cancellation_callback=None):
        """
        Executa conversão com progresso opcional.
        """

        def progress(value: int, message: str):
            if cancellation_callback and cancellation_callback():
                raise ConversionCancelledError("Conversão cancelada pelo usuário.")
            if progress_callback:
                progress_callback(value, message)

        source = ConvertService._canonical_format(job.source_format)
        target = ConvertService._canonical_format(job.target_format)
        key = f"{source}->{target}"

        if not ConvertService.supports(source, target):
            raise ValueError(f"Conversão não suportada: {key}")

        progress(0, "Iniciando conversão")

        # -------------------------
        # PDF
        # -------------------------

        if key == "PDF->JPG":
            progress(10, "Convertendo PDF para JPG")
            PDFService.convert_pdf_to_jpg(job, progress)

        elif key == "PDF->DOCX":
            progress(10, "Convertendo PDF para DOCX")
            PDFService.convert_pdf_to_docx(job, progress)

        # -------------------------
        # DOCX
        # -------------------------

        elif key == "DOCX->PDF":
            progress(10, "Convertendo DOCX para PDF")
            DOCService.convert_docx_to_pdf(job, progress)

        elif key == "DOCX->JPG":
            progress(10, "Convertendo DOCX para JPG")
            DOCService.convert_docx_to_jpg(job, progress)

        # -------------------------
        # PLANILHAS
        # -------------------------

        elif key == "XLSX->CSV":
            progress(10, "Convertendo XLSX para CSV")
            XLSXService.convert_xlsx_to_csv(job, progress)

        elif key == "CSV->XLSX":
            progress(10, "Convertendo CSV para XLSX")
            CSVService.convert_csv_to_xlsx(job, progress)

        # -------------------------
        # TEXTO
        # -------------------------

        elif key == "TXT->PDF":
            progress(10, "Convertendo TXT para PDF")
            TXTService.convert_txt_to_pdf(job, progress)

        # -------------------------
        # IMAGENS
        # -------------------------

        elif key == "JPG->PDF":
            progress(10, "Convertendo JPG para PDF")
            ImageService.image_to_pdf(job, progress)

        elif key == "PNG->PDF":
            progress(10, "Convertendo PNG para PDF")
            ImageService.image_to_pdf(job, progress)

        elif key == "TIFF->PDF":
            progress(10, "Convertendo TIFF para PDF")
            ImageService.image_to_pdf(job, progress)

        elif key == "PNG->JPG":
            progress(10, "Convertendo PNG para JPG")
            ImageService.image_to_jpg(job, progress)

        elif key == "TIFF->JPG":
            progress(10, "Convertendo TIFF para JPG")
            ImageService.image_to_jpg(job, progress)

        # -------------------------
        # NÃO SUPORTADO
        # -------------------------

        progress(100, "Conversão finalizada")

    @staticmethod
    def _canonical_format(value: str) -> str:
        normalized = value.strip().lstrip(".").upper()
        return {"JPEG": "JPG", "TIF": "TIFF"}.get(normalized, normalized)
