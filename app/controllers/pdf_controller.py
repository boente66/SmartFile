import os
import tempfile
from pathlib import Path
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from pypdf import PdfReader

from app.views.pdf_view import PDFView
from app.services.pdf_edit_service import PDFEditService
from app.services.pdf_preview_service import PDFPreviewService
from app.utils.file_naming import safe_output_path


class PDFController:
    """
    PDF Tools – edição em memória, salvar apenas no final.
    """

    def __init__(self, workspace):
        self.workspace = workspace
        self.view = PDFView()

        self._input_pdf: Path | None = None
        self._pages: list[int] = []   # estado da sessão
        self._rotations: dict[int, int] = {}
        self._temporary_files: set[Path] = set()

        self._connect_signals()
        self.workspace.register_view("pdf", self.view)

    # -------------------------
    # Navegação
    # -------------------------
    def activate(self):
        self.workspace.show_view("pdf")

    def open_document(self, path: str):
        """Abre o PDF Tools e carrega o documento informado."""
        self.activate()
        self.on_open_pdf(path)

    # -------------------------
    # Conexões
    # -------------------------
    def _connect_signals(self):
        self.view.open_pdf_requested.connect(self.on_open_pdf)
        self.view.remove_pages_requested.connect(self.on_remove_pages)
        self.view.reorder_pages_requested.connect(self.on_reorder_pages)
        self.view.save_pdf_requested.connect(self.on_save_pdf)
        self.view.add_files_requested.connect(self.on_add_files)
        self.view.rotate_pages_requested.connect(self.on_rotate_pages)
        self.view.extract_pages_requested.connect(self.on_extract_pages)
        self.view.split_pdf_requested.connect(self.on_split_pdf)
        self.view.merge_pdfs_requested.connect(self.on_merge_pdfs)
        self.view.back_requested.connect(lambda: self.workspace.show_view("documents"))

    # -------------------------
    # Abrir PDF
    # -------------------------
    def on_open_pdf(self, path: str):

        pdf_path = Path(path)

        if not pdf_path.exists():
            QMessageBox.warning(self.view, "PDF", "Arquivo não encontrado.")
            return

        try:
            reader = PdfReader(pdf_path)
        except Exception as e:
            QMessageBox.critical(self.view, "Erro ao abrir PDF", str(e))
            return

        self._input_pdf = pdf_path
        self._pages = list(range(len(reader.pages)))
        self._rotations = {}

        self._refresh_preview()

    def on_add_files(self, paths: list[str]):
        files = [Path(path) for path in paths]
        if not files:
            return
        if self._input_pdf is None:
            self.on_open_pdf(str(files[0]))
            if len(files) == 1:
                return
            files = files[1:]
        try:
            current = self._materialize_session()
            merged = self._temporary_pdf()
            PDFEditService.merge_pdfs([current, *files], merged)
            self._discard_temporary(current)
            self.on_open_pdf(str(merged))
        except Exception as exc:
            QMessageBox.critical(self.view, "Adicionar PDFs", str(exc))

    # -------------------------
    # Remover páginas
    # -------------------------
    def on_remove_pages(self, pages: list[int]):

        if not self._pages:
            return

        pages = set(pages)

        self._pages = [p for p in self._pages if p not in pages]

        self._refresh_preview()

    # -------------------------
    # Reordenar páginas
    # -------------------------
    def on_reorder_pages(self, order: list[int]):

        if not order:
            return

        self._pages = order
        self._refresh_preview()

    def on_rotate_pages(self, pages: list[int]):
        for page in pages:
            self._rotations[page] = (self._rotations.get(page, 0) + 90) % 360
        self._refresh_preview()

    def on_extract_pages(self, pages: list[int], output_path: str):
        if self._input_pdf is None:
            return
        try:
            output = safe_output_path(Path(output_path))
            order = [page for page in self._pages if page in set(pages)]
            PDFEditService.compose_pages(self._input_pdf, output, order, self._rotations)
            QMessageBox.information(self.view, "Extrair páginas", "Páginas extraídas com sucesso.")
        except Exception as exc:
            QMessageBox.critical(self.view, "Extrair páginas", str(exc))

    def on_split_pdf(self, output_directory: str):
        if self._input_pdf is None:
            return
        try:
            outputs = PDFEditService.split_pdf(
                self._input_pdf, Path(output_directory), self._pages, self._rotations
            )
            QMessageBox.information(self.view, "Dividir PDF", f"{len(outputs)} arquivo(s) criado(s).")
        except Exception as exc:
            QMessageBox.critical(self.view, "Dividir PDF", str(exc))

    def on_merge_pdfs(self, paths: list[str], output_path: str):
        try:
            output = safe_output_path(Path(output_path))
            PDFEditService.merge_pdfs([Path(path) for path in paths], output)
            self.on_open_pdf(str(output))
            self._cleanup_temporaries()
        except Exception as exc:
            QMessageBox.critical(self.view, "Mesclar PDFs", str(exc))

    # -------------------------
    # Salvar PDF
    # -------------------------
    def on_save_pdf(self):

        if not self._input_pdf:
            QMessageBox.warning(self.view, "Salvar", "Nenhum PDF carregado.")
            return

        if not self._pages:
            QMessageBox.warning(self.view, "Salvar", "Todas as páginas foram removidas.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Salvar PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if not path:
            return

        output = safe_output_path(Path(path))

        try:

            PDFEditService.compose_pages(
                input_file=self._input_pdf,
                output_file=output,
                page_order=self._pages,
                rotations=self._rotations,
            )

            QMessageBox.information(
                self.view,
                "Sucesso",
                "PDF salvo com sucesso."
            )
            self.on_open_pdf(str(output))
            self._cleanup_temporaries()

        except Exception as e:

            QMessageBox.critical(
                self.view,
                "Erro ao salvar PDF",
                str(e)
            )

    # -------------------------
    # Atualizar preview
    # -------------------------
    def _refresh_preview(self):

        if not self._input_pdf:
            return

        try:

            images = PDFPreviewService.generate_thumbnails(
                self._input_pdf,
                self._pages,
                rotations=self._rotations,
            )

            pixmaps: list[QPixmap] = [
                QPixmap.fromImage(img) for img in images
            ]

            self.view.load_pdf(str(self._input_pdf))
            self.view.show_thumbnails(pixmaps, self._pages)

        except Exception as e:

            QMessageBox.critical(
                self.view,
                "Erro ao gerar preview",
                str(e)
            )

    def _temporary_pdf(self) -> Path:
        descriptor, name = tempfile.mkstemp(prefix="smartfile_pdf_", suffix=".pdf")
        os.close(descriptor)
        path = Path(name)
        self._temporary_files.add(path)
        return path

    def _materialize_session(self) -> Path:
        if self._input_pdf is None:
            raise ValueError("Nenhum PDF carregado.")
        temporary = self._temporary_pdf()
        PDFEditService.compose_pages(
            self._input_pdf, temporary, self._pages, self._rotations
        )
        return temporary

    def _discard_temporary(self, path: Path) -> None:
        if path in self._temporary_files:
            try:
                path.unlink(missing_ok=True)
            finally:
                self._temporary_files.discard(path)

    def _cleanup_temporaries(self) -> None:
        for path in list(self._temporary_files):
            self._discard_temporary(path)
