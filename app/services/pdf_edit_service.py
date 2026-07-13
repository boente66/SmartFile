# app/services/pdf_edit_service.py

from pathlib import Path
from pypdf import PdfReader, PdfWriter

from app.utils.file_naming import safe_output_path


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

    @staticmethod
    def compose_pages(
        input_file: Path,
        output_file: Path,
        page_order: list[int],
        rotations: dict[int, int] | None = None,
    ):
        """Materializa ordem e rotações da sessão em um novo PDF."""
        if input_file.resolve() == output_file.resolve():
            raise ValueError("Entrada e saída não podem ser o mesmo arquivo")
        reader = PdfReader(input_file)
        writer = PdfWriter()
        total_pages = len(reader.pages)
        for index in page_order:
            if index < 0 or index >= total_pages:
                raise ValueError(f"Página inválida: {index}")
            page = reader.pages[index]
            rotation = (rotations or {}).get(index, 0) % 360
            if rotation:
                page.rotate(rotation)
            writer.add_page(page)
        with output_file.open("wb") as handle:
            writer.write(handle)

    @staticmethod
    def split_pdf(
        input_file: Path,
        output_dir: Path,
        page_order: list[int] | None = None,
        rotations: dict[int, int] | None = None,
    ) -> list[Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        reader = PdfReader(input_file)
        order = page_order if page_order is not None else list(range(len(reader.pages)))
        outputs = []
        for position, page_index in enumerate(order, start=1):
            output = safe_output_path(output_dir / f"{input_file.stem}_pagina_{position}.pdf")
            writer = PdfWriter()
            page = reader.pages[page_index]
            rotation = (rotations or {}).get(page_index, 0) % 360
            if rotation:
                page.rotate(rotation)
            writer.add_page(page)
            with output.open("wb") as handle:
                writer.write(handle)
            outputs.append(output)
        return outputs

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
