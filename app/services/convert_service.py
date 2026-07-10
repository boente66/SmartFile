# app/services/convert_service.py

from app.services.pdf_service import PDFService
from app.services.doc_service import DOCService
from app.services.xlsx_service import XLSXService
from app.services.csv_service import CSVService
from app.services.txt_service import TXTService
from app.services.image_service import ImageService


class ConvertService:

    @staticmethod
    def execute(job, progress_callback=None):
        """
        Executa conversão com progresso opcional.
        """

        def progress(value: int, message: str):
            if progress_callback:
                progress_callback(value, message)

        key = job.conversion_key

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
        # DOC
        # -------------------------

        elif key == "DOC->PDF":
            progress(10, "Convertendo DOC para PDF")
            DOCService.convert_doc_to_pdf(job, progress)

        elif key == "DOC->JPG":
            progress(10, "Convertendo DOC para JPG")
            DOCService.convert_doc_to_jpg(job, progress)

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

        else:
            raise ValueError(f"Conversão não suportada: {key}")

        progress(100, "Conversão finalizada")
