from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox, QFileDialog

from app.services.audit_service import AuditService
from app.services.organization_admin_service import OrganizationAdminService
from app.services.organization_feature_service import OrganizationFeatureService
from app.views.organization_audit_dialog import OrganizationAuditDialog
from app.views.organization_dialog import OrganizationDialog
from app.views.corporate_design_dialog import CorporateDesignDialog
from app.services.organization_identity_service import OrganizationIdentityService
from app.services.audit_report_service import AuditReportService
from app.workers.file_operation_worker import FileOperationWorker
from app.delivery.delivery_http_client import DeliveryHttpClient
from pathlib import Path

logger = logging.getLogger(__name__)


class OrganizationSettingsController(QObject):
    """Entrada administrativa para organização, recursos e infraestrutura."""

    organization_changed = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self, document_service, session_context, *, parent=None,
        refresh_callback=None, transport_controller=None,
    ):
        super().__init__(parent)
        self.document_service = document_service
        self.database = document_service.database
        self.session_context = session_context
        self.parent_widget = parent
        self.refresh_callback = refresh_callback
        self.transport_controller = transport_controller
        self.admin = OrganizationAdminService(self.database, session_context)
        self.features = OrganizationFeatureService(self.database, session_context)
        self.identity = OrganizationIdentityService(self.database,session_context)
        self.audit = AuditService(self.database,session_context)
        self.reports = AuditReportService(self.database,session_context)
        self._workers=set()
        self._identity_worker=None
        self._closing=False
        self._timer=QTimer(self)
        self._timer.setInterval(60000)
        self._timer.timeout.connect(self.synchronize_identity)
        self._timer.start()
        QTimer.singleShot(0,self.synchronize_identity)

    def activate_organization(self, organization_id: int) -> None:
        try:
            organization = self.document_service.set_active_organization(
                int(organization_id)
            )
            self.session_context.set_active_organization(organization)
            self._refresh()
            self.status_changed.emit(f"Organização ativa: {organization.name}")
            self.organization_changed.emit(int(organization.id))
        except Exception as exc:
            self._report_failure(exc)

    def create_organization(self) -> None:
        name, accepted = QInputDialog.getText(
            self.parent_widget, "Nova organização", "Nome:"
        )
        if not accepted:
            return
        template_name, accepted = QInputDialog.getItem(
            self.parent_widget, "Modelo inicial", "Estrutura de pastas:",
            ["Pessoal", "Estudante", "Empresarial", "Começar vazio"],
            3, False,
        )
        if not accepted:
            return
        template_code = {
            "Pessoal": "PERSONAL", "Estudante": "STUDENT",
            "Empresarial": "BUSINESS", "Começar vazio": "EMPTY",
        }[template_name]
        plan_name, accepted = QInputDialog.getItem(
            self.parent_widget, "Plano de armazenamento", "Cota lógica:",
            ["Pessoal — 10 GB", "Estudante — 20 GB", "Empresarial — 60 GB"],
            {"PERSONAL": 0, "STUDENT": 1, "BUSINESS": 2, "EMPTY": 0}[template_code],
            False,
        )
        if not accepted:
            return
        plan_code = {
            "Pessoal — 10 GB": "PERSONAL_10GB",
            "Estudante — 20 GB": "STUDENT_20GB",
            "Empresarial — 60 GB": "BUSINESS_60GB",
        }[plan_name]
        try:
            organization = self.admin.create(
                name, template=template_code, profile_code=template_code,
                storage_plan_code=plan_code, activate=True,
            )
            self.document_service.set_active_organization(organization.id)
            self._refresh()
            self.status_changed.emit(f"Organização criada: {organization.name}")
            self.organization_changed.emit(int(organization.id))
        except Exception as exc:
            self._report_failure(exc)

    def open_general_settings(self) -> None:
        try:
            organization = self.document_service.organization_service.active()
            dialog = OrganizationDialog(
                self.parent_widget, organization, show_template=False,
                enabled_features=self.features.for_organization(organization).codes,
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            values = dialog.values()
            updated = self.admin.update(
                organization.id, values["name"], values["description"],
                values["icon"], values["color"], values["profile_code"],
                values["enabled_features"],
            )
            self.session_context.set_active_organization(updated)
            self._refresh()
            self.status_changed.emit(
                f"Perfil de recursos atualizado: {updated.profile_code}"
            )
        except Exception as exc:
            self._report_failure(exc)

    def delete_organization(self) -> None:
        try:
            organization = self.document_service.organization_service.active()
            self.session_context.require_permission("organization.update")
            answer = QMessageBox.question(
                self.parent_widget, "Excluir organização",
                f"Deseja excluir a organização ‘{organization.name}’? "
                "Os arquivos internos não serão apagados.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self.document_service.organization_service.delete(organization.id)
            replacement = self.document_service.organization_service.active()
            self.session_context.set_active_organization(replacement)
            self._refresh()
            self.status_changed.emit(f"Organização ativa: {replacement.name}")
            self.organization_changed.emit(int(replacement.id))
        except Exception as exc:
            self._report_failure(exc)

    def open_infrastructure_settings(self) -> None:
        if self.transport_controller is None:
            self.failed.emit("Configuração de transporte indisponível.")
            return
        self.transport_controller.open_configuration(
            self.document_service.active_organization_id
        )

    def open_security_history(self) -> None:
        try:
            organization_id=self.document_service.active_organization_id
            self.identity._admin(organization_id)
            rows=self.audit.list_for_organization(organization_id,5000)
            dialog=OrganizationAuditDialog(rows,self.parent_widget,identity=self.identity.get(organization_id))
            def query(filters):
                try:dialog.set_rows(self.audit.list_for_organization(organization_id,5000,**filters))
                except Exception as exc:dialog.info.setText(str(exc))
            def export(kind):
                extension=kind.lower()
                path,_=QFileDialog.getSaveFileName(dialog,'Exportar auditoria',f'auditoria.{extension}',f'{kind} (*.{extension})')
                if path:
                    filters=dialog.values()
                    self._operation(lambda:self.reports.export(organization_id,path,kind,filters),
                        lambda _:dialog.info.setText('Relatório exportado.'),organization_id,dialog)
            dialog.query_requested.connect(query);dialog.export_requested.connect(export)
            dialog.exec()
        except Exception as exc:self._report_failure(exc)

    def _operation(self,task,completed,organization_id,dialog=None):
        worker=FileOperationWorker(lambda _progress,_cancelled:task(),audit_actor=self.audit.capture(organization_id))
        self._workers.add(worker)
        def current():
            return not self._closing and organization_id==getattr(self.session_context.active_organization,'id',None) and (dialog is None or dialog.isVisible())
        worker.succeeded.connect(lambda value:completed(value) if current() else None)
        worker.failed.connect(lambda message:dialog.error.setText(message) if current() and hasattr(dialog,'error') else self.status_changed.emit(message) if current() else None)
        worker.finished.connect(lambda:self._workers.discard(worker));worker.finished.connect(worker.deleteLater)
        worker.start()
        return worker

    def open_corporate_design(self):
        try:
            organization_id=self.document_service.active_organization_id
            self.identity._admin(organization_id)
            dialog=CorporateDesignDialog(self.identity.get(organization_id),self.identity.instances.repository.list_peers(organization_id),self.identity.source(organization_id),self.parent_widget)
            def preview(values):
                try:dialog.preview.apply_identity(self.identity.preview(organization_id,values));dialog.error.clear()
                except Exception as exc:dialog.error.setText(str(exc))
            def image(kind,path):
                try:
                    if Path(path).stat().st_size>self.identity.MAX_IMAGE_INPUT:raise ValueError('Imagem excede 5 MB.')
                    dialog.set_image(kind,self.identity.normalize_image(Path(path).read_bytes(),kind))
                except Exception as exc:dialog.error.setText(str(exc))
            def saved(identity):
                dialog.load_identity(identity);dialog.error.setText('Identidade salva. SmartFile permanece identificado.');self._refresh()
            def save(values,source):
                try:
                    if source is None:
                        self.identity.preview(organization_id,values)
                        with self.database.transaction():
                            if self.identity.source(organization_id):self.identity.detach_source(organization_id)
                            identity=self.identity.save(organization_id,values)
                        saved(identity)
                    elif self.identity.source(organization_id) and self.identity.source(organization_id)['instance_id']==source:
                        self._operation(lambda:self.identity.synchronize(organization_id),saved,organization_id,dialog)
                    else:
                        peer=self.identity.instances.repository.find_by_instance_id(source)
                        local=self.identity.instances.local(organization_id)
                        def confirm(package):
                            proposed=self.identity._validate_package(source,package)
                            answer=QMessageBox.question(dialog,'Vincular identidade institucional',
                                f'Usar {proposed.title()} (CNPJ {proposed.cnpj or "não informado"}) da instalação {source}? Confirme que é a mesma organização. A fonte controla a identidade nas instalações vinculadas.',
                                QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
                            if answer==QMessageBox.StandardButton.Yes:
                                try:saved(self.identity.bind_source(organization_id,source,package))
                                except Exception as exc:dialog.error.setText(str(exc))
                        self._operation(lambda:DeliveryHttpClient(timeout=5).organization_identity(peer.current_ip,peer.http_port,local.instance_id),confirm,organization_id,dialog)
                except Exception as exc:dialog.error.setText(str(exc))
            dialog.preview_requested.connect(preview);dialog.image_requested.connect(image);dialog.save_requested.connect(save)
            dialog.exec()
        except Exception as exc:self._report_failure(exc)

    def synchronize_identity(self):
        if self._closing or self._identity_worker is not None or self.session_context is None or not self.session_context.is_authenticated():return
        organization_id=getattr(self.session_context.active_organization,'id',None)
        if not organization_id or not self.identity.source(organization_id):return
        self._identity_worker=self._operation(lambda:self.identity.synchronize(organization_id),lambda _:self._refresh(),organization_id)
        self._identity_worker.finished.connect(lambda:setattr(self,'_identity_worker',None))

    def shutdown(self):
        self._closing=True;self._timer.stop()
        for worker in list(self._workers):worker.requestInterruption();worker.wait()

    def _refresh(self) -> None:
        if self.refresh_callback is not None:
            self.refresh_callback()

    def _report_failure(self, exc: Exception) -> None:
        message = str(exc).strip() or "Falha nas configurações da organização."
        logger.warning("organization.settings.controller.failed", exc_info=True)
        self.failed.emit(message)
