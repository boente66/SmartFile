from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QDialog, QInputDialog, QMessageBox

from app.services.audit_service import AuditService
from app.services.organization_admin_service import OrganizationAdminService
from app.services.organization_feature_service import OrganizationFeatureService
from app.views.organization_audit_dialog import OrganizationAuditDialog
from app.views.organization_dialog import OrganizationDialog

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
            self.session_context.require_permission("audit.view")
            rows = AuditService(self.database).list_for_organization(
                self.document_service.active_organization_id, 50,
            )
            OrganizationAuditDialog(rows, self.parent_widget).exec()
        except Exception as exc:
            self._report_failure(exc)

    def _refresh(self) -> None:
        if self.refresh_callback is not None:
            self.refresh_callback()

    def _report_failure(self, exc: Exception) -> None:
        message = str(exc).strip() or "Falha nas configurações da organização."
        logger.warning("organization.settings.controller.failed", exc_info=True)
        self.failed.emit(message)
