from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.controllers.convert_controller import ConvertController
from app.controllers.pdf_controller import PDFController
from app.services.document_service import DocumentService
from app.views.document_view import DocumentView


class DocumentController:
    def __init__(self, workspace, main_view, convert_controller: Optional[ConvertController] = None, pdf_controller: Optional[PDFController] = None):
        self.workspace = workspace
        self.main_view = main_view
        self.view = DocumentView()
        self.service = DocumentService()
        self.convert_controller = convert_controller
        self.pdf_controller = pdf_controller
        self._current_search = ""
        self._current_type = "Todos"

        self._connect_signals()
        self._register_view()

    def _connect_signals(self):
        self.view.import_requested.connect(self.on_import_document)
        self.view.search_requested.connect(self.on_search_documents)
        self.view.filter_requested.connect(self.on_filter_documents)
        self.view.refresh_requested.connect(self.on_refresh_documents)
        self.view.open_requested.connect(self.on_open_document)
        self.view.convert_requested.connect(self.on_convert_document)
        self.view.pdf_tools_requested.connect(self.on_pdf_tools_document)
        self.view.delete_requested.connect(self.on_delete_document)
        self.view.favorite_requested.connect(self.on_toggle_favorite)
        self.view.document_selected.connect(self.on_document_selected)

    def _register_view(self):
        self.workspace.register_view("documents", self.view)

    def activate(self):
        self.workspace.show_view("documents")
        self.on_refresh_documents()

    def on_import_document(self):
        path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Importar documento",
            "",
            "Todos os arquivos (*)",
        )
        if not path:
            return

        try:
            self.service.import_document(path)
            self.view.set_status("Documento importado com sucesso")
            self.on_refresh_documents()
        except Exception as exc:
            QMessageBox.warning(self.view, "Mini GED", str(exc))

    def on_search_documents(self, term: str):
        self._current_search = term
        self._refresh_documents()

    def on_filter_documents(self, file_type: str):
        self._current_type = file_type
        self._refresh_documents()

    def on_refresh_documents(self):
        self._refresh_documents()

    def on_open_document(self, document_id: int):
        try:
            document = self.service.open_document(document_id)
            self._open_file(document.path)
            self.view.set_status(f"Documento aberto: {document.name}")
        except FileNotFoundError as exc:
            QMessageBox.warning(self.view, "Mini GED", str(exc))
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def on_document_selected(self, document_id: int):
        document = self.service.get_document(document_id)
        self.view.show_document_details(document)

    def on_convert_document(self, document_id: int):
        document = self.service.get_document(document_id)
        if document is None:
            return

        if self.convert_controller is None:
            QMessageBox.warning(self.view, "Mini GED", "Módulo de conversão não está disponível.")
            return

        self.convert_controller.open_document(document.path)
        self.view.set_status(f"Arquivo enviado para conversão: {document.name}")

    def on_pdf_tools_document(self, document_id: int):
        document = self.service.get_document(document_id)
        if document is None:
            return

        if self.pdf_controller is None:
            QMessageBox.warning(self.view, "Mini GED", "Módulo de PDF Tools não está disponível.")
            return

        if document.path.lower().endswith(".pdf"):
            self.pdf_controller.open_document(document.path)
        else:
            QMessageBox.information(self.view, "Mini GED", "PDF Tools é indicado para arquivos PDF.")
        self.view.set_status(f"Arquivo enviado para PDF Tools: {document.name}")

    def on_delete_document(self, document_id: int):
        confirm = QMessageBox.question(
            self.view,
            "Excluir registro",
            "Deseja remover este registro do Mini GED?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self.service.delete_document(document_id)
            if deleted:
                self.view.set_status("Registro removido com sucesso")
                self.on_refresh_documents()
            else:
                QMessageBox.warning(self.view, "Mini GED", "Registro não encontrado.")
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def on_toggle_favorite(self, document_id: int):
        try:
            document = self.service.toggle_favorite(document_id)
            self._refresh_documents()
            self.view.set_status(f"Favorito atualizado: {document.name}")
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def _refresh_documents(self):
        if self._current_type and self._current_type != "Todos":
            documents = self.service.filter_by_type(self._current_type)
        else:
            documents = self.service.list_documents()

        if self._current_search:
            documents = [document for document in documents if self._current_search.lower() in document.name.lower() or self._current_search.lower() in (document.category or "").lower()]

        self.view.set_documents(documents)
        self.view.show_document_details(None)
        if not documents:
            self.view.set_status("Nenhum documento encontrado")
        else:
            self.view.set_status(f"{len(documents)} documento(s) registrado(s)")

    def _open_file(self, path: str):
        document_path = Path(path)
        if not document_path.exists():
            raise FileNotFoundError("O arquivo não existe mais no caminho registrado.")

        if sys.platform.startswith("win"):
            os.startfile(document_path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(document_path)])
        else:
            subprocess.Popen(["xdg-open", str(document_path)])
