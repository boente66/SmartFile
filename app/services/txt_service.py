# app/services/txt_service.py

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.models.convert_job import ConvertJob


class TXTService:
    """
    Serviço responsável por conversão TXT → PDF.
    """

    @staticmethod
    def convert_txt_to_pdf(job: ConvertJob, progress=None):

        if progress:
            progress(10, "Abrindo arquivo TXT")

        c = canvas.Canvas(str(job.output_path), pagesize=A4)

        width, height = A4
        y = height - 40

        with open(job.input_path, "r", encoding="utf-8") as f:

            lines = f.readlines()
            total = len(lines)

            text = c.beginText(40, y)

            for i, line in enumerate(lines):

                text.textLine(line.rstrip())
                y -= 14

                # quebra de página
                if y < 40:
                    c.drawText(text)
                    c.showPage()

                    text = c.beginText(40, height - 40)
                    y = height - 40

                if progress:
                    value = int(((i + 1) / total) * 100)
                    progress(value, f"Processando linha {i+1}/{total}")

        c.drawText(text)
        c.save()

        if progress:
            progress(100, "TXT convertido para PDF")