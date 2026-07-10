# app/services/pdf_edit_service.py

from pathlib import Path
from pypdf import PdfReader, PdfWriter


class PDFEditService:
    """
    Serviço responsável pela manipulação estrutural de PDFs.

    Não realiza conversão de formato.
    """

    # -------------------------
    # Mesclar PDFs
    # -------------------------
    @staticmethod
    def merge_pdfs(input_files: list[Path], output_file: Path):

        if not input_files:
            raise ValueError("Nenhum arquivo PDF informado")

        writer = PdfWriter()

        for pdf_path in input_files:

            if not pdf_path.exists():
                raise FileNotFoundError(f"Arquivo não encontrado: {pdf_path}")

            reader = PdfReader(pdf_path)

            for page in reader.pages:
                writer.add_page(page)

        with open(output_file, "wb") as f:
            writer.write(f)

    # -------------------------
    # Remover páginas
    # -------------------------
    @staticmethod
    def remove_pages(
        input_file: Path,
        output_file: Path,
        pages_to_remove: list[int]
    ):

        if input_file.resolve() == output_file.resolve():
            raise ValueError("Entrada e saída não podem ser o mesmo arquivo")

        reader = PdfReader(input_file)
        writer = PdfWriter()

        pages_to_remove = set(pages_to_remove)

        for index, page in enumerate(reader.pages):

            if index not in pages_to_remove:
                writer.add_page(page)

        with open(output_file, "wb") as f:
            writer.write(f)

    # -------------------------
    # Extrair páginas
    # -------------------------
    @staticmethod
    def extract_pages(
        input_file: Path,
        output_file: Path,
        pages_to_extract: list[int]
    ):

        reader = PdfReader(input_file)
        writer = PdfWriter()

        total_pages = len(reader.pages)

        for index in pages_to_extract:

            if index < 0 or index >= total_pages:
                raise ValueError(f"Página inválida: {index}")

            writer.add_page(reader.pages[index])

        with open(output_file, "wb") as f:
            writer.write(f)

    # -------------------------
    # Reordenar páginas
    # -------------------------
    @staticmethod
    def reorder_pages(
        input_file: Path,
        output_file: Path,
        new_order: list[int]
    ):

        reader = PdfReader(input_file)
        writer = PdfWriter()

        total_pages = len(reader.pages)

        for index in new_order:

            if index < 0 or index >= total_pages:
                raise ValueError(f"Página inválida: {index}")

            writer.add_page(reader.pages[index])

        with open(output_file, "wb") as f:
            writer.write(f)

    # -------------------------
    # Rotacionar páginas
    # -------------------------
    @staticmethod
    def rotate_pages(
        input_file: Path,
        output_file: Path,
        pages: list[int],
        rotation: int
    ):
        """
        Rotaciona páginas do PDF.

        rotation: 90, 180, 270
        """

        if rotation not in (90, 180, 270):
            raise ValueError("Rotação inválida (use 90, 180 ou 270)")

        reader = PdfReader(input_file)
        writer = PdfWriter()

        pages = set(pages)

        for index, page in enumerate(reader.pages):

            if index in pages:
                page.rotate(rotation)

            writer.add_page(page)

        with open(output_file, "wb") as f:
            writer.write(f)

    # -------------------------
    # Compressão de PDF
    # -------------------------
    @staticmethod
    def compress_pdf(
        input_file: Path,
        output_file: Path
    ):
        """
        Reduz tamanho do PDF comprimindo streams.
        """

        reader = PdfReader(input_file)
        writer = PdfWriter()

        for page in reader.pages:

            # comprime conteúdo da página
            try:
                page.compress_content_streams()
            except Exception:
                pass

            writer.add_page(page)

        # remove metadados
        writer.add_metadata({})

        with open(output_file, "wb") as f:
            writer.write(f)