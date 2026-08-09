from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from app.services.organization_transport_service import OrganizationTransportService
from app.views.organization_transport_dialog import OrganizationTransportDialog
from app.workers.transport_worker import TransportWorker

logger = logging.getLogger(__name__)


class CorporateTransportController(QObject):
    """Controla configuração e testes administrativos do transporte."""

    configuration_saved = pyqtSignal(int)
    retry_enqueued = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self, database, session_context, *, parent=None,
        organization_id_provider=None,
        dialog_factory=OrganizationTransportDialog,
        worker_factory=TransportWorker,
        service=None,
    ):
        super().__init__(parent)
        self.service = service or OrganizationTransportService(
            database, session_context
        )
        self.session_context = session_context
        self.parent_widget = parent
        self.organization_id_provider = organization_id_provider
        self.dialog_factory = dialog_factory
        self.worker_factory = worker_factory
        self.dialog = None
        self._test_worker = None
        self._organization_id: int | None = None

    def open_configuration(
        self, organization_id: int | None = None, *, modal: bool = True,
    ):
        try:
            self._organization_id = int(
                organization_id or self._active_organization_id()
            )
            settings = self.service.get(self._organization_id)
            summary = self.service.summary(self._organization_id)
            dialog = self.dialog_factory(settings, summary, self.parent_widget)
            self.dialog = dialog
            dialog.test_requested.connect(self.test_connection)
            dialog.retry_requested.connect(self.retry_failed)
            dialog.accepted.connect(self.save_configuration)
            if modal:
                dialog.exec()
                if self.dialog is dialog:
                    self.dialog = None
            else:
                dialog.show()
            return dialog
        except Exception as exc:
            self._report_failure(exc)
            return None

    def save_configuration(self) -> None:
        if self.dialog is None or self._organization_id is None:
            return
        try:
            self.service.configure(
                self._organization_id, **self.dialog.values()
            )
            self.status_changed.emit("Configuração de transporte atualizada")
            self.configuration_saved.emit(self._organization_id)
        except Exception as exc:
            self._report_failure(exc)

    def test_connection(self, values: dict):
        if self.dialog is None or self._organization_id is None:
            return None
        if self._test_worker is not None and self._test_worker.isRunning():
            self.dialog.show_test_result(False, "Já existe um teste em andamento.")
            return None
        dialog = self.dialog
        organization_id = self._organization_id
        dialog.set_test_busy(True)
        worker = self.worker_factory(
            lambda _progress, _cancelled: self.service.test_connection(
                organization_id, values["mode"], values["endpoint"],
            )
        )
        self._test_worker = worker
        worker.succeeded.connect(
            lambda result, dialog=dialog: dialog.show_test_result(
                result.success, result.message
            )
        )
        worker.failed.connect(
            lambda message, dialog=dialog: dialog.show_test_result(False, message)
        )
        worker.finished.connect(lambda dialog=dialog: dialog.set_test_busy(False))
        worker.finished.connect(lambda worker=worker: self._cleanup_test_worker(worker))
        worker.finished.connect(worker.deleteLater)
        worker.start()
        return worker

    def retry_failed(self) -> None:
        if self.dialog is None or self._organization_id is None:
            return
        try:
            count = self.service.retry_failed(self._organization_id)
            self.dialog.show_summary(self.service.summary(self._organization_id))
            self.status_changed.emit(
                f"{count} job(s) preparado(s) para nova tentativa"
            )
            if count:
                self.retry_enqueued.emit(self._organization_id)
        except Exception as exc:
            self._report_failure(exc)

    def shutdown(self, wait_ms: int = 5_000) -> None:
        worker = self._test_worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            if not worker.wait(wait_ms):
                logger.warning("corporate.transport.controller.shutdown_timeout")

    def _cleanup_test_worker(self, worker) -> None:
        if self._test_worker is worker:
            self._test_worker = None

    def _report_failure(self, exc: Exception) -> None:
        message = str(exc).strip() or "Falha no transporte corporativo."
        logger.warning("corporate.transport.controller.failed", exc_info=True)
        self.failed.emit(message)

    def _active_organization_id(self) -> int:
        if self.organization_id_provider is not None:
            return int(self.organization_id_provider())
        organization = getattr(self.session_context, "active_organization", None)
        if organization is None:
            raise RuntimeError("Nenhuma organização ativa.")
        return int(organization.id)
