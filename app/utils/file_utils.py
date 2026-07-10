import os
import time
from pathlib import Path

from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import pandas as pd
from pdf2docx import Converter
from pdf2image import convert_from_path


# -------------------------
# LOG AUXILIAR
# -------------------------

def _log(message):
    print(f"[FileConvert] {message}")


# -------------------------
# PDF → DOCX
# -------------------------

def convert_pdf_to_docx(file_path, output_path):
    try:
        _log(f"Start conversion: {file_path}")

        cv = Converter(str(file_path))

        _log("Analyzing document...")
        time.sleep(0.5)

        cv.convert(str(output_path), start=0, end=None)
        cv.close()

        _log("PDF → DOCX conversion completed")
        return True

    except Exception as e:
        _log(f"ERROR PDF→DOCX: {e}")
        return False


# -------------------------
# JPG → PDF
# -------------------------

def convert_jpg_to_pdf(file_path, output_path):
    try:
        _log(f"Start conversion: {file_path}")

        image = Image.open(file_path)

        if image.mode != "RGB":
            image = image.convert("RGB")

        image.save(output_path, "PDF", resolution=100.0)

        _log("JPG → PDF conversion completed")
        return True

    except Exception as e:
        _log(f"ERROR JPG→PDF: {e}")
        return False


# -------------------------
# XLSX → CSV
# -------------------------

def convert_xlsx_to_csv(file_path, output_path):
    try:
        _log(f"Start conversion: {file_path}")

        df = pd.read_excel(file_path)
        df.to_csv(output_path, index=False)

        _log("XLSX → CSV conversion completed")
        return True

    except Exception as e:
        _log(f"ERROR XLSX→CSV: {e}")
        return False


# -------------------------
# PDF → JPG
# -------------------------

def convert_pdf_to_jpg(file_path, output_dir):
    try:
        _log(f"Start conversion: {file_path}")

        images = convert_from_path(file_path)

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for i, image in enumerate(images):
            output_file = output_dir / f"page_{i + 1}.jpg"
            image.save(output_file, "JPEG")

        _log("PDF → JPG conversion completed")
        return True

    except Exception as e:
        _log(f"ERROR PDF→JPG: {e}")
        return False


# -------------------------
# DOCX → PDF
# -------------------------

def convert_docx_to_pdf(file_path, output_path):
    try:
        _log(f"Start conversion: {file_path}")

        from docx2pdf import convert

        convert(file_path, output_path)

        _log("DOCX → PDF conversion completed")
        return True

    except Exception as e:
        _log(f"ERROR DOCX→PDF: {e}")
        return False
