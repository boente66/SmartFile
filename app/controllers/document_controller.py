from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app.controllers.convert_controller import ConvertController
from app.controllers.pdf_controller import PDFController
from app.controllers.pdf_viewer_controller import PDFViewerController
from app.services.document_service import DocumentService
from app.views.document_view import DocumentView
from app.workers.cloud_sync_worker import CloudSyncWorker
from app.cloud.cloud_oauth_config_service import CloudOAuthConfigService
from app.cloud.cloud_python_auth_service import CloudPythonAuthService
from app.views.cloud_api_settings_dialog import CloudApiSettingsDialog
from app.workers.cloud_auth_worker import CloudAuthWorker
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.services.folder_template_service import FolderTemplateService
from app.cloud.cloud_models import CloudOAuthState
from app.errors.cloud_exceptions import CloudConfigurationMissingError, CloudPermissionError


class DocumentController:
    def __init__(self, workspace, main_view, convert_controller: Optional[ConvertController] = None, pdf_controller: Optional[PDFController] = None, pdf_viewer_controller: Optional[PDFViewerController] = None, session_context=None, document_service=None):
        self.workspace = workspace
        self.main_view = main_view
        self.view = DocumentView()
        self.service = document_service or DocumentService()
        self.convert_controller = convert_controller
        self.pdf_controller = pdf_controller
        self.pdf_viewer_controller = pdf_viewer_controller
        self.session_context = session_context
        self.service.cloud_manager.session_context = session_context
        self._current_search = ""
        self._current_type = "Todos"
        self._current_folder_id: int | None = None
        self._current_scope = "documents"
        self._cloud_worker = None
        self._cloud_auth_worker = None
        self._copied_document_id = None
        self._cloud_timer = QTimer(self.view)
        self._cloud_timer.setInterval(60_000)
        self._cloud_timer.timeout.connect(self._auto_sync)
        self._cloud_timer.start()

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
        self.view.cloud_provider_changed.connect(self.on_cloud_provider_changed)
        self.view.add_cloud_account_requested.connect(self.on_add_cloud_account)
        self.view.sync_now_requested.connect(self.on_sync_now)
        self.view.pause_sync_requested.connect(lambda: self.on_pause_sync(True))
        self.view.resume_sync_requested.connect(lambda: self.on_pause_sync(False))
        self.view.disconnect_cloud_requested.connect(self.on_disconnect_cloud)
        self.view.cloud_history_requested.connect(self.on_cloud_history)
        self.view.cloud_login_requested.connect(self.on_add_cloud_account)
        self.view.cloud_oauth_settings_requested.connect(self.on_configure_cloud_oauth)
        self.view.copy_requested.connect(self.on_copy_document)
        self.view.paste_requested.connect(self.on_paste_document)
        self.view.restore_requested.connect(self.on_restore_document)
        self.view.permanent_delete_requested.connect(self.on_permanent_delete_document)
        self.view.empty_trash_requested.connect(self.on_empty_trash)
        self.view.recalculate_storage_requested.connect(self.on_recalculate_storage)
        self.view.largest_files_requested.connect(self.on_largest_files)
        self.view.change_storage_plan_requested.connect(self.on_change_storage_plan)

    def _register_view(self):
        self.workspace.register_view("documents", self.view)

    def activate(self):
        self.main_view.sidebar.hide()
        self.workspace.show_view("documents")
        self._refresh_organizations()
        self.view.apply_cloud_permissions(self.session_context)
        self._refresh_folders()
        self._refresh_cloud()
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
            self._auto_sync()
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
            if self.session_context:
                self.session_context.set_active_organization(organization)
            self._current_folder_id = None
            self._refresh_folders()
            self._refresh_cloud()
            self._refresh_documents()
            self.view.set_status(f"Organização ativa: {organization.name}")
        except Exception as exc:
            QMessageBox.warning(self.view, "Organizações", str(exc))

    def on_create_organization(self):
        name, accepted = QInputDialog.getText(self.view, "Nova organização", "Nome:")
        if not accepted:
            return
        template_name, template_accepted = QInputDialog.getItem(
            self.view, "Modelo inicial", "Estrutura de pastas:",
            ["Pessoal", "Estudante", "Empresarial", "Começar vazio"], 3, False,
        )
        if not template_accepted:
            return
        template_code = {
            "Pessoal": "PERSONAL", "Estudante": "STUDENT",
            "Empresarial": "BUSINESS", "Começar vazio": "EMPTY",
        }[template_name]
        plan_name, plan_accepted = QInputDialog.getItem(
            self.view, "Plano de armazenamento", "Cota lógica:",
            ["Pessoal — 10 GB", "Estudante — 20 GB", "Empresarial — 60 GB"],
            {"PERSONAL": 0, "STUDENT": 1, "BUSINESS": 2, "EMPTY": 0}[template_code], False,
        )
        if not plan_accepted:
            return
        plan_code = {
            "Pessoal — 10 GB": "PERSONAL_10GB", "Estudante — 20 GB": "STUDENT_20GB",
            "Empresarial — 60 GB": "BUSINESS_60GB",
        }[plan_name]
        try:
            with self.service.database.transaction():
                organization = self.service.organization_service.create(
                    name, template_code=template_code, storage_plan_code=plan_code
                )
                FolderTemplateService(self.service.folder_service).create_template_folders(
                    organization.id, template_code
                )
                if self.session_context and self.session_context.current_user:
                    now = self.service._now()
                    membership = OrganizationMemberRepository(database=self.service.database).create(
                        OrganizationMemberEntity(
                            organization_id=organization.id,
                            user_id=self.session_context.current_user.id,
                            role="OWNER", created_at=now, updated_at=now,
                        )
                    )
                    self.session_context.memberships.append(membership)
            self.service.set_active_organization(organization.id)
            if self.session_context:
                self.session_context.set_active_organization(organization)
            self._current_folder_id = None
            self._refresh_organizations()
            self._refresh_folders()
            self._refresh_cloud()
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

    def on_cloud_provider_changed(self, provider: str):
        try:
            if provider == "LOCAL":
                self.service.cloud_manager.configure(self.service.active_organization_id, "LOCAL")
            else:
                account = self.service.cloud_manager.active_account_for(
                    provider, self.service.active_organization_id
                )
                if account is None:
                    QMessageBox.information(
                        self.view, "Camada de Nuvem",
                        "Adicione uma conta antes de ativar este provedor."
                    )
                else:
                    self.service.cloud_manager.configure(
                        self.service.active_organization_id, provider, account.id
                    )
            self._refresh_cloud()
            self._refresh_documents()
        except Exception as exc:
            QMessageBox.warning(self.view, "Camada de Nuvem", str(exc))
            self._refresh_cloud()

    def on_add_cloud_account(self,provider=None):
        provider = str(provider or self.view.cloud_combo.currentData())
        index=self.view.cloud_combo.findData(provider)
        if index>=0:
            self.view.cloud_combo.blockSignals(True)
            self.view.cloud_combo.setCurrentIndex(index)
            self.view.cloud_combo.blockSignals(False)
        if provider == "LOCAL":
            QMessageBox.information(
                self.view, "Adicionar conta", "Selecione OneDrive ou Google Drive."
            )
            return
        if self._cloud_auth_worker is not None:
            QMessageBox.information(self.view,"Adicionar conta","Já existe uma autenticação em andamento.")
            return
        try:
            self._require_cloud_permission("cloud.connect")
            config=CloudOAuthConfigService(self.service.database)
            if not config.is_configured(provider):
                self._refresh_cloud(provider)
                raise CloudConfigurationMissingError(
                    f"A integração com o {config.display_name(provider)} ainda não foi configurada "
                    "pelo administrador do SmartFile."
                )
            settings = self.service.cloud_manager.settings(self.service.active_organization_id)
            self.view.set_cloud_settings(settings, None, CloudOAuthState.AUTHENTICATING)
            service=CloudPythonAuthService(self.service.database); worker=CloudAuthWorker(service,provider); self._cloud_auth_worker=worker
            worker.progress.connect(lambda _value,message:self.view.set_status(message))
            worker.succeeded.connect(lambda result,p=provider,w=worker:self._on_cloud_auth_succeeded(p,result,w))
            worker.failed.connect(lambda message,p=provider,w=worker:self._on_cloud_auth_failed(p,message,w))
            worker.finished.connect(lambda w=worker:self._cleanup_cloud_auth_worker(w)); worker.start()
        except Exception as exc: QMessageBox.warning(self.view,"Adicionar conta",str(exc))

    def _on_cloud_auth_succeeded(self,provider,result,worker):
        if worker is not self._cloud_auth_worker:return
        try:
            self.service.cloud_manager.save_authentication_result(self.service.active_organization_id,provider,result); self._refresh_cloud(); self.view.set_status(f"{CloudOAuthConfigService.display_name(provider)} conectado com sucesso.")
        except Exception as exc:QMessageBox.warning(self.view,"Adicionar conta",str(exc))

    def _on_cloud_auth_failed(self,provider,message,worker):
        if worker is self._cloud_auth_worker:
            self.service.cloud_manager._audit(
                "CLOUD_CONNECT_FAILED", self.service.active_organization_id, None,
                f"Autorização {provider} não concluída",
            )
            self._refresh_cloud(provider)
            QMessageBox.warning(self.view,"Autenticação da nuvem",message)
            self.view.set_status("Autenticação da nuvem não concluída")

    def _cleanup_cloud_auth_worker(self,worker):
        if self._cloud_auth_worker is worker:self._cloud_auth_worker=None; worker.deleteLater()

    def on_configure_cloud_oauth(self):
        try:
            if self.session_context is None or not self.session_context.is_system_admin():
                raise CloudPermissionError(
                    "Somente o administrador do sistema pode configurar provedores OAuth."
                )
            dialog = CloudApiSettingsDialog(
                CloudOAuthConfigService(self.service.database),
                self.view,
                str(self.view.cloud_combo.currentData() or "ONEDRIVE"),
            )
            dialog.exec()
            self._refresh_cloud()
        except Exception as exc:
            QMessageBox.warning(self.view, "Configuração OAuth", str(exc))

    def on_sync_now(self):
        try:
            self._require_cloud_permission("cloud.sync")
        except CloudPermissionError as exc:
            QMessageBox.warning(self.view, "Sincronização", str(exc))
            return
        if self._cloud_worker is not None:
            QMessageBox.information(self.view, "Sincronização", "Já existe uma sincronização em andamento.")
            return
        settings = self.service.cloud_manager.settings(self.service.active_organization_id)
        if settings.sync_mode == "LOCAL":
            QMessageBox.information(self.view, "Sincronização", "Esta organização utiliza somente armazenamento local.")
            return
        worker = CloudSyncWorker(self.service.cloud_sync_service, self.service.active_organization_id)
        self._cloud_worker = worker
        worker.progress.connect(lambda value, message: self.main_view.progress.update(value, message))
        worker.succeeded.connect(self._on_cloud_sync_succeeded)
        worker.failed.connect(self._on_cloud_sync_failed)
        worker.finished.connect(lambda worker=worker: self._cleanup_cloud_worker(worker))
        worker.finished.connect(worker.deleteLater)
        self.main_view.progress.start("Sincronizando documentos")
        worker.start()

    def on_pause_sync(self, paused: bool):
        self.service.cloud_manager.set_paused(self.service.active_organization_id, paused)
        self._refresh_cloud()
        self.view.set_status("Sincronização pausada" if paused else "Sincronização retomada")

    def on_disconnect_cloud(self):
        try:
            self._require_cloud_permission("cloud.disconnect")
        except CloudPermissionError as exc:
            QMessageBox.warning(self.view, "Desconectar nuvem", str(exc))
            return
        answer = QMessageBox.question(
            self.view, "Remover conta da nuvem",
            "Remover o login da nuvem desta organização? Os tokens locais serão apagados e os documentos locais serão preservados."
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.service.cloud_manager.remove_account(self.service.active_organization_id)
            self._refresh_cloud()

    def on_cloud_history(self):
        rows = self.service.database.fetch_all(
            """
            SELECT sync_jobs.* FROM sync_jobs JOIN documents ON documents.id = sync_jobs.document_id
            WHERE documents.organization_id = ? ORDER BY sync_jobs.id DESC LIMIT 20
            """,
            (self.service.active_organization_id,),
        )
        message = "\n".join(
            f"#{row['id']} {row['operation']} — {row['status']}"
            for row in rows
        ) or "Nenhuma operação de nuvem registrada."
        QMessageBox.information(self.view, "Histórico da nuvem", message)

    def _on_cloud_sync_succeeded(self, result):
        self.main_view.progress.finish("Sincronização concluída")
        self._refresh_cloud(); self._refresh_documents()
        self.view.set_status(f"Sincronização concluída: {result['jobs']} job(s)")

    def _on_cloud_sync_failed(self, message: str):
        self.main_view.progress.finish("Falha na sincronização")
        QMessageBox.warning(self.view, "Sincronização", message)

    def _cleanup_cloud_worker(self, worker):
        if self._cloud_worker is worker:
            self._cloud_worker = None

    def on_copy_document(self,document_id): self._copied_document_id=document_id; self.view.set_status("Documento copiado. Escolha a pasta e use Colar.")
    def on_paste_document(self):
        if self._copied_document_id is None: QMessageBox.information(self.view,"Colar","Nenhum documento foi copiado."); return
        try:self.service.copy_document(self._copied_document_id,self._current_folder_id); self._refresh_documents(); self.view.set_status("Cópia criada com sucesso")
        except Exception as exc:QMessageBox.warning(self.view,"Colar",str(exc))
    def on_restore_document(self,document_id):
        try:self.service.restore_document(document_id); self._refresh_documents(); self.view.set_status("Documento restaurado")
        except Exception as exc:QMessageBox.warning(self.view,"Lixeira",str(exc))
    def on_permanent_delete_document(self,document_id):
        if QMessageBox.question(self.view,"Excluir definitivamente","Esta ação não pode ser desfeita. Continuar?")!=QMessageBox.StandardButton.Yes:return
        try:self.service.permanently_delete_document(document_id); self._refresh_documents()
        except Exception as exc:QMessageBox.warning(self.view,"Lixeira",str(exc))
    def on_empty_trash(self):
        if QMessageBox.question(self.view,"Esvaziar lixeira","Excluir definitivamente todos os documentos da lixeira?")!=QMessageBox.StandardButton.Yes:return
        try:count=self.service.empty_trash(); self._refresh_documents(); self.view.set_status(f"Lixeira esvaziada: {count} documento(s)")
        except Exception as exc:QMessageBox.warning(self.view,"Lixeira",str(exc))

    def on_recalculate_storage(self):
        try:
            self.service.recalculate_storage_usage()
            self._refresh_storage()
            self.view.set_status("Uso do armazenamento recalculado")
        except Exception as exc:
            QMessageBox.warning(self.view, "Armazenamento", str(exc))

    def on_largest_files(self):
        documents = self.service.get_largest_documents()
        message = "\n".join(
            f"{index}. {item.name} — {self.view._format_size(item.size)}"
            for index, item in enumerate(documents, 1)
        ) or "Nenhum documento armazenado."
        QMessageBox.information(self.view, "Arquivos maiores", message)

    def on_change_storage_plan(self):
        try:
            if self.session_context:
                self.session_context.require_permission("organization.update")
            plans = self.service.storage_quota_service.plans.find_all()
            labels = [plan.name for plan in plans]
            selected, accepted = QInputDialog.getItem(
                self.view, "Alterar plano", "Plano de armazenamento lógico:", labels, 0, False
            )
            if not accepted:
                return
            plan = plans[labels.index(selected)]
            organization = self.service.organization_service.active()
            self.service.storage_quota_service.assign_plan(
                organization.id, plan.code, organization.template_code
            )
            self._refresh_storage()
            self.view.set_status(f"Plano alterado para {plan.name}")
        except Exception as exc:
            QMessageBox.warning(self.view, "Armazenamento", str(exc))

    def _auto_sync(self):
        settings = self.service.cloud_manager.settings(self.service.active_organization_id)
        if (
            settings.sync_mode != "LOCAL"
            and not settings.paused
            and self.service.cloud_sync_service.queue.pending_count(
                self.service.active_organization_id
            ) > 0
            and self._cloud_worker is None
        ):
            self.on_sync_now()

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
        if self._current_scope == "trash":
            self.on_permanent_delete_document(document_id)
            return
        confirm = QMessageBox.question(
            self.view,
            "Mover para lixeira",
            "Deseja mover este documento para a lixeira?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = self.service.delete_document(document_id)
            if deleted:
                self.view.set_status("Documento movido para a lixeira")
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
        self._refresh_storage()
        self.view.show_document_details(None)
        if not documents:
            self.view.set_status("Nenhum documento encontrado")
        else:
            self.view.set_status(f"{len(documents)} documento(s) registrado(s)")

    def _refresh_organizations(self):
        organizations = self.service.organization_service.list_organizations()
        if self.session_context and self.session_context.is_authenticated():
            allowed = {membership.organization_id for membership in self.session_context.memberships}
            organizations = [organization for organization in organizations if organization.id in allowed]
        self.view.set_organizations(organizations, self.service.active_organization_id)

    def _refresh_folders(self):
        organization = self.service.organization_service.active()
        folders = self.service.folder_service.list_folders(organization.id)
        self.view.set_folders(organization.name, folders)

    def _refresh_cloud(self, selected_provider=None):
        settings = self.service.cloud_manager.settings(self.service.active_organization_id)
        account = None
        if settings.cloud_account_id:
            try:
                account = self.service.cloud_manager.account(settings.cloud_account_id)
            except Exception:
                account = None
        provider = selected_provider or (account.provider if account else None)
        if provider in {"ONEDRIVE", "GOOGLE_DRIVE"}:
            state = self.service.cloud_manager.authentication_state(
                self.service.active_organization_id, provider
            )
        else:
            state = CloudOAuthState.DISCONNECTED
        self.view.set_cloud_settings(settings, account, state)

    def _require_cloud_permission(self, permission: str) -> None:
        if self.session_context is None:
            return
        try:
            self.session_context.require_permission(permission)
        except Exception as exc:
            raise CloudPermissionError(
                "Você não possui permissão para conectar uma conta de nuvem nesta organização."
            ) from exc

    def _refresh_storage(self):
        self.view.set_storage_usage(self.service.get_storage_usage())

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
