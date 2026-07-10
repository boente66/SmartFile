from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.services.ged_service import delete_document, list_documents, rename_document
from app.views.ged_view import GEDView


class GEDController:
    """Controller do Mini GED para organização de documentos."""

    def __init__(self, workspace, main_view):
        self.workspace = workspace
        self.main_view = main_view
        self.view = GEDView()
        self._folder: Path | None = None

        self._connect_signals()
        self._register_view()
        self._set_default_folder()

    def _connect_signals(self):
        self.view.folder_requested.connect(self.on_select_folder)
        self.view.refresh_requested.connect(self.on_refresh)
        self.view.open_requested.connect(self.on_open_document)
        self.view.rename_requested.connect(self.on_rename_document)
        self.view.delete_requested.connect(self.on_delete_document)

    def _register_view(self):
        self.workspace.register_view("ged", self.view)

    def activate(self):
        self.workspace.show_view("ged")
        self.on_refresh()

    def on_select_folder(self):
        start_path = str(self._folder or Path.home())
        folder = QFileDialog.getExistingDirectory(
            self.view,
            "Selecionar pasta do Mini GED",
            start_path,
        )

        if not folder:
            return

        self._folder = Path(folder)
        self.view.set_folder(str(self._folder))
        self.on_refresh()

    def on_refresh(self):
        if self._folder is None:
            self._set_default_folder()

        if self._folder is None:
            self.view.set_summary("Nenhuma pasta selecionada")
            self.view.set_documents([])
            return

        documents = list_documents(self._folder, search=self.view.search_text())
        self.view.set_documents(documents)

        if not documents:
            self.view.set_summary(f"Nenhum documento encontrado em {self._folder}")
            return

        self.view.set_summary(
            f"{len(documents)} documento(s) encontrado(s) em {self._folder}"
        )

    def on_open_document(self, path: str):
        document_path = Path(path)
        if not document_path.exists():
            QMessageBox.warning(self.view, "Mini GED", "O arquivo selecionado não existe mais.")
            return

        try:
            if sys.platform.startswith("win"):
                os.startfile(document_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(document_path)])
            else:
                subprocess.Popen(["xdg-open", str(document_path)])
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", f"Não foi possível abrir o arquivo: {exc}")

    def on_rename_document(self, path: str, new_name: str):
        try:
            rename_document(path, new_name)
            self.view.set_summary("Documento renomeado com sucesso.")
            self.on_refresh()
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def on_delete_document(self, path: str):
        document_path = Path(path)
        if not document_path.exists():
            QMessageBox.warning(self.view, "Mini GED", "O arquivo selecionado não existe mais.")
            return

        confirm = QMessageBox.question(
            self.view,
            "Excluir documento",
            f"Deseja excluir {document_path.name}?",
        )

        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_document(document_path)
            self.view.set_summary("Documento removido com sucesso.")
            self.on_refresh()
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def _set_default_folder(self):
        project_root = Path(__file__).resolve().parents[2]
        self._folder = project_root
        self.view.set_folder(str(self._folder))
