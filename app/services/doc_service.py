# app/services/doc_service.py

import os
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from pathlib import Path

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

        if sys.platform.startswith("linux"):
            DOCService._convert_with_libreoffice(job)
        else:
            try:
                from docx2pdf import convert
            except ImportError as exc:
                raise RuntimeError(
                    "O componente DOCX para PDF não está instalado."
                ) from exc
            convert(str(job.input_path), str(job.output_path))

        if progress:
            progress(90, "DOCX convertido para PDF")

    # -------------------------
    # DOCX → JPG
    # -------------------------
    @staticmethod
    def convert_docx_to_jpg(job: ConvertJob, progress=None):
        with TemporaryDirectory(
            prefix="smartfile-docx-", dir=job.output_path.parent
        ) as directory:
            temp_pdf = Path(directory) / f"{job.input_path.stem}.pdf"
            pdf_job = ConvertJob(
                input_path=job.input_path,
                output_path=temp_pdf,
                source_format="DOCX",
                target_format="PDF",
            )

            if progress:
                progress(10, "Convertendo DOCX para PDF")

            DOCService.convert_docx_to_pdf(pdf_job)

            if progress:
                progress(40, "Gerando imagens")

            images = convert_from_path(temp_pdf)
            outputs = DOCService._jpg_output_paths(job.output_path, len(images))
            DOCService._ensure_outputs_available(outputs)
            try:
                for index, (image, output_file) in enumerate(
                    zip(images, outputs), start=1
                ):
                    image.save(output_file, "JPEG")
                    if progress:
                        value = 40 + int((index / len(images)) * 50)
                        progress(
                            value,
                            f"Convertendo página {index}/{len(images)}",
                        )
            finally:
                for image in images:
                    image.close()

    @staticmethod
    def _convert_with_libreoffice(job: ConvertJob) -> None:
        executable = shutil.which("libreoffice") or shutil.which("soffice")
        if executable is None:
            raise RuntimeError(
                "A conversão DOCX para PDF no Linux requer o LibreOffice. "
                "Instale o pacote 'libreoffice' e tente novamente."
            )
        output_path = job.output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(
            prefix="smartfile-libreoffice-", dir=output_path.parent
        ) as directory:
            try:
                result = subprocess.run(
                    [
                        executable,
                        "--headless",
                        "--convert-to",
                        "pdf",
                        "--outdir",
                        directory,
                        str(job.input_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "O LibreOffice excedeu o tempo limite de cinco minutos."
                ) from exc
            produced = Path(directory) / f"{job.input_path.stem}.pdf"
            if result.returncode != 0 or not produced.is_file():
                detail = (result.stderr or result.stdout).strip()[:300]
                suffix = f" Detalhes: {detail}" if detail else ""
                raise RuntimeError(
                    "O LibreOffice não conseguiu converter o documento."
                    + suffix
                )
            os.replace(produced, output_path)

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

    @staticmethod
    def _ensure_outputs_available(paths: list[Path]) -> None:
        existing = next((path for path in paths if path.exists()), None)
        if existing:
            raise FileExistsError(f"O arquivo de saída já existe: {existing}")
