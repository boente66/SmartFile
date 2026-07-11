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

        self._refresh_preview()

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

            PDFEditService.reorder_pages(
                input_file=self._input_pdf,
                output_file=output,
                new_order=self._pages
            )

            QMessageBox.information(
                self.view,
                "Sucesso",
                "PDF salvo com sucesso."
            )

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
                self._pages
            )

            pixmaps: list[QPixmap] = [
                QPixmap.fromImage(img) for img in images
            ]

            self.view.load_pdf(str(self._input_pdf))
            self.view.show_thumbnails(pixmaps)

        except Exception as e:

            QMessageBox.critical(
                self.view,
                "Erro ao gerar preview",
                str(e)
            )
