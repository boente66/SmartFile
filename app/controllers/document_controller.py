from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app.controllers.convert_controller import ConvertController
from app.controllers.pdf_controller import PDFController
from app.controllers.pdf_viewer_controller import PDFViewerController
from app.services.document_service import DocumentService
from app.views.document_view import DocumentView


class DocumentController:
    def __init__(self, workspace, main_view, convert_controller: Optional[ConvertController] = None, pdf_controller: Optional[PDFController] = None, pdf_viewer_controller: Optional[PDFViewerController] = None):
        self.workspace = workspace
        self.main_view = main_view
        self.view = DocumentView()
        self.service = DocumentService()
        self.convert_controller = convert_controller
        self.pdf_controller = pdf_controller
        self.pdf_viewer_controller = pdf_viewer_controller
        self._current_search = ""
        self._current_type = "Todos"
        self._current_folder_id: int | None = None
        self._current_scope = "documents"

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
        self.view.organization_changed.connect(self.on_organization_changed)
        self.view.create_organization_requested.connect(self.on_create_organization)
        self.view.edit_organization_requested.connect(self.on_edit_organization)
        self.view.delete_organization_requested.connect(self.on_delete_organization)
        self.view.folder_selected.connect(self.on_folder_selected)
        self.view.create_folder_requested.connect(self.on_create_folder)
        self.view.rename_folder_requested.connect(self.on_rename_folder)
        self.view.delete_folder_requested.connect(self.on_delete_folder)
        self.view.scanner_requested.connect(self.on_open_scanner)
        self.view.visualize_requested.connect(self.on_open_document)
        self.view.sign_requested.connect(self.on_sign_document)
        self.view.scope_changed.connect(self.on_scope_changed)

    def _register_view(self):
        self.workspace.register_view("documents", self.view)

    def activate(self):
        self.workspace.show_view("documents")
        self._refresh_organizations()
        self._refresh_folders()
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
            self.service.import_document(path, self._current_folder_id)
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
            if document.path.lower().endswith(".pdf") and self.pdf_viewer_controller:
                self.pdf_viewer_controller.open_document(document.path)
            else:
                self._open_file(document.path)
            self.view.set_status(f"Documento aberto: {document.name}")
        except FileNotFoundError as exc:
            QMessageBox.warning(self.view, "Mini GED", str(exc))
        except Exception as exc:
            QMessageBox.critical(self.view, "Mini GED", str(exc))

    def on_document_selected(self, document_id: int):
        document = self.service.get_document(document_id)
        self.view.show_document_details(document)

    def on_organization_changed(self, organization_id: int):
        try:
            organization = self.service.set_active_organization(organization_id)
            self._current_folder_id = None
            self._refresh_folders()
            self._refresh_documents()
            self.view.set_status(f"Organização ativa: {organization.name}")
        except Exception as exc:
            QMessageBox.warning(self.view, "Organizações", str(exc))

    def on_create_organization(self):
        name, accepted = QInputDialog.getText(self.view, "Nova organização", "Nome:")
        if not accepted:
            return
        try:
            organization = self.service.organization_service.create(name)
            self.service.set_active_organization(organization.id)
            self._current_folder_id = None
            self._refresh_organizations()
            self._refresh_folders()
            self._refresh_documents()
        except Exception as exc:
            QMessageBox.warning(self.view, "Organizações", str(exc))

    def on_edit_organization(self):
        organization = self.service.organization_service.active()
        name, accepted = QInputDialog.getText(
            self.view, "Editar organização", "Nome:", text=organization.name
        )
        if not accepted:
            return
        try:
            self.service.organization_service.update(organization.id, name, organization.description)
            self._refresh_organizations()
            self._refresh_folders()
        except Exception as exc:
            QMessageBox.warning(self.view, "Organizações", str(exc))

    def on_delete_organization(self):
        organization = self.service.organization_service.active()
        answer = QMessageBox.question(
            self.view,
            "Excluir organização",
            f"Deseja excluir a organização ‘{organization.name}’? Os arquivos internos não serão apagados.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.organization_service.delete(organization.id)
            self._current_folder_id = None
            self._refresh_organizations()
            self._refresh_folders()
            self._refresh_documents()
        except Exception as exc:
            QMessageBox.warning(self.view, "Organizações", str(exc))

    def on_folder_selected(self, folder_id):
        self._current_folder_id = int(folder_id) if folder_id is not None else None
        self._refresh_documents()

    def on_scope_changed(self, scope: str):
        self._current_scope = scope
        if scope not in {"documents", "folders"}:
            self._current_folder_id = None
        self._refresh_documents()

    def on_create_folder(self):
        name, accepted = QInputDialog.getText(self.view, "Nova pasta", "Nome:")
        if not accepted:
            return
        try:
            self.service.folder_service.create(
                self.service.active_organization_id, name, self._current_folder_id
            )
            self._refresh_folders()
        except Exception as exc:
            QMessageBox.warning(self.view, "Pastas", str(exc))

    def on_rename_folder(self):
        if self._current_folder_id is None:
            QMessageBox.information(self.view, "Pastas", "Selecione uma pasta para renomear.")
            return
        folder = self.service.folder_service.repository.find_by_id(
            self._current_folder_id, self.service.active_organization_id
        )
        if folder is None:
            return
        name, accepted = QInputDialog.getText(
            self.view, "Renomear pasta", "Nome:", text=folder.name
        )
        if not accepted:
            return
        try:
            self.service.folder_service.rename(
                self.service.active_organization_id, folder.id, name
            )
            self._refresh_folders()
        except Exception as exc:
            QMessageBox.warning(self.view, "Pastas", str(exc))

    def on_delete_folder(self):
        if self._current_folder_id is None:
            QMessageBox.information(self.view, "Pastas", "Selecione uma pasta para excluir.")
            return
        answer = QMessageBox.question(
            self.view, "Excluir pasta", "Excluir esta pasta lógica e suas subpastas?"
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete_folder(self._current_folder_id)
            self._current_folder_id = None
            self._refresh_folders()
            self._refresh_documents()
        except Exception as exc:
            QMessageBox.warning(self.view, "Pastas", str(exc))

    def on_open_scanner(self):
        self.main_view.sidebar.set_active_tool("scanner")
        self.main_view.sidebar.tool_selected.emit("scanner")

    def on_sign_document(self, document_id: int):
        document = self.service.get_document(document_id)
        if document is None or not document.path.lower().endswith(".pdf"):
            QMessageBox.information(self.view, "Assinar", "Selecione um documento PDF.")
            return
        if self.pdf_viewer_controller is None:
            QMessageBox.warning(self.view, "Assinar", "Visualizador de PDF indisponível.")
            return
        self.pdf_viewer_controller.open_document(document.path)

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
        if self._current_scope == "favorites" and not self._current_search:
            documents = self.service.get_favorite_documents()
        elif self._current_scope == "recent" and not self._current_search:
            documents = self.service.get_recent_documents()
        elif self._current_scope == "trash" and not self._current_search:
            documents = self.service.get_trashed_documents()
        else:
            documents = self.service.search_documents(
                self._current_search,
                self._current_type,
                self._current_folder_id,
            )

        self.view.set_documents(documents)
        self.view.show_document_details(None)
        if not documents:
            self.view.set_status("Nenhum documento encontrado")
        else:
            self.view.set_status(f"{len(documents)} documento(s) registrado(s)")

    def _refresh_organizations(self):
        organizations = self.service.organization_service.list_organizations()
        self.view.set_organizations(organizations, self.service.active_organization_id)

    def _refresh_folders(self):
        organization = self.service.organization_service.active()
        folders = self.service.folder_service.list_folders(organization.id)
        self.view.set_folders(organization.name, folders)

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
