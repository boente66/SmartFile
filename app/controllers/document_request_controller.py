from __future__ import annotations

import logging

from app.services.document_request_service import DocumentRequestService
from app.views.document_requests_dialog import DocumentRequestsDialog

logger = logging.getLogger(__name__)


class DocumentRequestController:
    """Orquestra a UI de solicitações sem mover regras para a apresentação."""

    def __init__(
        self, database, session_context, *, parent=None,
        organization_id_provider=None, dialog_factory=DocumentRequestsDialog,
        service=None,
    ):
        self.service = service or DocumentRequestService(database, session_context)
        self.session_context = session_context
        self.parent = parent
        self.organization_id_provider = organization_id_provider
        self.dialog_factory = dialog_factory
        self.dialog = None
        self.organization_id: int | None = None

    def open_requests(
        self, organization_id: int | None = None, *, modal: bool = True,
    ):
        self.organization_id = int(
            organization_id or self._active_organization_id()
        )
        dialog = self.dialog_factory(self.parent)
        self.dialog = dialog
        dialog.create_requested.connect(self.create)
        dialog.status_update_requested.connect(self.update_status)
        self.refresh()
        if modal:
            dialog.exec()
            if self.dialog is dialog:
                self.dialog = None
        else:
            dialog.show()
        return dialog

    def refresh(self) -> None:
        if self.dialog is None or self.organization_id is None:
            return
        try:
            members = self.service.list_assignable_members(self.organization_id)
            requests = self.service.list_requests(self.organization_id)
            self.dialog.set_assignable_members(members)
            self.dialog.set_deadline_enabled(
                self.service.deadline_enabled(self.organization_id)
            )
            self.dialog.set_permissions(
                can_create=self.service.can_create(),
                can_update=self.service.can_update(),
            )
            self.dialog.set_requests(requests)
        except Exception as exc:
            logger.warning("document.requests.refresh_failed", exc_info=True)
            self.dialog.show_error(str(exc))

    def create(self, values: dict) -> None:
        if self.dialog is None or self.organization_id is None:
            return
        try:
            self.service.create(self.organization_id, **values)
            self.dialog.clear_create_form()
            self.refresh()
        except Exception as exc:
            logger.warning("document.requests.create_failed", exc_info=True)
            self.dialog.show_error(str(exc))

    def update_status(self, request_id: int, status: str) -> None:
        if self.dialog is None or self.organization_id is None:
            return
        try:
            self.service.set_status(self.organization_id, request_id, status)
            self.refresh()
        except Exception as exc:
            logger.warning("document.requests.update_failed", exc_info=True)
            self.dialog.show_error(str(exc))

    def _active_organization_id(self) -> int:
        if self.organization_id_provider is not None:
            return int(self.organization_id_provider())
        organization = getattr(self.session_context, "active_organization", None)
        if organization is None:
            raise RuntimeError("Nenhuma organização ativa.")
        return int(organization.id)
