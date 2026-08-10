from __future__ import annotations

import inspect
import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtTest import QSignalSpy
from PyQt6.QtWidgets import QApplication

from app.controllers.corporate_transport_controller import CorporateTransportController
from app.controllers.document_controller import DocumentController
from app.controllers.document_request_controller import DocumentRequestController
from app.coordinators.corporate_transport_coordinator import CorporateTransportCoordinator
from app.views.document_requests_dialog import DocumentRequestsDialog

_APPLICATION = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


@dataclass
class _Request:
    id: int = 1
    title: str = "Contrato"
    status: str = "OPEN"
    due_at: str | None = None
    assigned_to_user_id: int | None = None


class _RequestService:
    def __init__(self, *, can_create=True, can_update=True):
        self.created = []
        self.updated = []
        self.requests = [_Request()]
        self.members = [SimpleNamespace(id=8, display_name="Responsável")]
        self._can_create = can_create
        self._can_update = can_update

    def list_assignable_members(self, _organization_id):
        return self.members

    def list_requests(self, _organization_id):
        return self.requests

    def deadline_enabled(self, _organization_id):
        return True

    def can_create(self):
        return self._can_create

    def can_update(self):
        return self._can_update

    def create(self, organization_id, **values):
        self.created.append((organization_id, values))

    def set_status(self, organization_id, request_id, status):
        self.updated.append((organization_id, request_id, status))


def test_request_view_emits_and_controller_executes_use_cases():
    app = _app()
    service = _RequestService()
    controller = DocumentRequestController(
        object(), object(), organization_id_provider=lambda: 4, service=service,
    )
    dialog = controller.open_requests(modal=False)

    assert dialog.assignee.count() == 2
    dialog.title.setText("Nota fiscal")
    dialog.assignee.setCurrentIndex(1)
    dialog.create_button.click()
    app.processEvents()
    assert service.created[0][0] == 4
    assert service.created[0][1]["title"] == "Nota fiscal"
    assert service.created[0][1]["assigned_to_user_id"] == 8

    dialog.list.setCurrentRow(0)
    dialog.status.setCurrentIndex(dialog.status.findData("COMPLETED"))
    dialog.update_button.click()
    app.processEvents()
    assert service.updated == [(4, 1, "COMPLETED")]
    dialog.close()


def test_request_controller_applies_permissions_and_view_has_no_service():
    _app()
    service = _RequestService(can_create=False, can_update=False)
    controller = DocumentRequestController(
        object(), object(), organization_id_provider=lambda: 3, service=service,
    )
    dialog = controller.open_requests(modal=False)
    assert not dialog.create_button.isEnabled()
    assert not dialog.update_button.isEnabled()
    assert not hasattr(dialog, "service")
    assert "DocumentRequestService" not in inspect.getsource(DocumentRequestsDialog)
    dialog.close()


class _TransportService:
    def __init__(self):
        self.configured = []
        self.tests = []
        self.retry_count = 2
        self.raise_on_configure = False
        self.settings = SimpleNamespace(
            mode="NAS", endpoint="/tmp/nas", enabled=True, verify_tls=True,
        )

    def get(self, _organization_id):
        return self.settings

    def summary(self, _organization_id):
        return {
            "mode": "NAS", "enabled": True, "pending": 1,
            "failed": self.retry_count, "last_test_message": None,
            "credential_configured": True,
        }

    def configure(self, organization_id, **values):
        if self.raise_on_configure:
            raise ValueError("Configuração inválida")
        self.configured.append((organization_id, values))

    def test_connection(self, organization_id, mode, endpoint):
        self.tests.append((organization_id, mode, endpoint))
        return SimpleNamespace(success=True, message="Destino acessível")

    def retry_failed(self, _organization_id):
        count = self.retry_count
        self.retry_count = 0
        return count


def test_transport_controller_opens_saves_tests_and_loads_summary():
    _app()
    service = _TransportService()
    controller = CorporateTransportController(
        object(), object(), organization_id_provider=lambda: 7, service=service,
    )
    dialog = controller.open_configuration(modal=False)
    assert "Jobs pendentes: 1" in dialog.transport_status.text()
    assert "Credencial configurada" in dialog.credential_status.text()
    assert dialog.credential_password.echoMode() == dialog.credential_password.EchoMode.Password
    assert not dialog.credential_username.text() and not dialog.credential_password.text()

    worker = controller.test_connection(dialog.values())
    assert worker.wait(3_000)
    _app().processEvents()
    assert service.tests == [(7, "NAS", "/tmp/nas")]
    assert "Conectado" in dialog.transport_status.text()

    dialog.credential_username.setText("usuario")
    dialog.credential_password.setText("segredo-transitorio")
    dialog.accept()
    assert service.configured and service.configured[0][0] == 7
    assert service.configured[0][1]["credential_password"] == "segredo-transitorio"
    assert not dialog.credential_username.text() and not dialog.credential_password.text()


def test_transport_controller_reports_configuration_error_and_retries():
    _app()
    service = _TransportService()
    controller = CorporateTransportController(
        object(), object(), organization_id_provider=lambda: 2, service=service,
    )
    failures = QSignalSpy(controller.failed)
    retries = QSignalSpy(controller.retry_enqueued)
    dialog = controller.open_configuration(modal=False)
    controller.retry_failed()
    assert retries and retries[0] == [2]
    service.raise_on_configure = True
    dialog.accept()
    assert failures and failures[0] == ["Configuração inválida"]


class _Queue:
    def __init__(self, pending=True):
        self.pending = pending

    def next_pending(self, _organization_id):
        return object() if self.pending else None


class _CorporateService:
    def __init__(self, pending=True):
        self.queue = _Queue(pending)
        self.processed = []

    def process_pending(self, organization_id, progress, cancelled):
        self.processed.append(organization_id)
        progress(100, "Concluído")
        return {"jobs": 1, "completed": 1, "retry": 0, "failed": 0}

    def automatic_processing_enabled(self, _organization_id):
        return True


class _ControlledWorker(QObject):
    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, task, *, finish_immediately=False):
        super().__init__()
        self.task = task
        self.running = False
        self.interrupted = False
        self.finish_immediately = finish_immediately

    def start(self):
        self.running = True
        if self.finish_immediately:
            result = self.task(self.progress.emit, lambda: self.interrupted)
            self.succeeded.emit(result)
            self.complete()

    def isRunning(self):
        return self.running

    def requestInterruption(self):
        self.interrupted = True

    def wait(self, _milliseconds):
        return not self.running

    def complete(self):
        self.running = False
        self.finished.emit()


def _coordinator(tmp_path: Path, *, pending=True, immediate=False):
    CorporateTransportCoordinator._active_workers.clear()
    context = SimpleNamespace(
        active_organization=SimpleNamespace(id=1),
        is_authenticated=lambda: True,
    )
    service = _CorporateService(pending)
    workers = []

    def factory(task):
        worker = _ControlledWorker(task, finish_immediately=immediate)
        workers.append(worker)
        return worker

    coordinator = CorporateTransportCoordinator(
        SimpleNamespace(db_name=str(tmp_path / "app.db")), context,
        service=service, worker_factory=factory,
    )
    return coordinator, context, service, workers


def test_transport_coordinator_starts_only_for_pending_job(tmp_path: Path):
    _app()
    coordinator, _context, _service, workers = _coordinator(tmp_path)
    assert coordinator.trigger()
    assert len(workers) == 1
    assert not coordinator.trigger()
    assert len(workers) == 1
    workers[0].complete()

    coordinator, _context, _service, workers = _coordinator(
        tmp_path / "empty", pending=False,
    )
    assert not coordinator.trigger()
    assert workers == []


def test_transport_coordinator_shutdown_interrupts_worker(tmp_path: Path):
    _app()
    coordinator, _context, _service, workers = _coordinator(tmp_path)
    coordinator.trigger()
    coordinator.shutdown(wait_ms=0)
    assert workers[0].interrupted
    workers[0].complete()


def test_transport_coordinator_switches_organization_safely(tmp_path: Path):
    app = _app()
    coordinator, context, _service, workers = _coordinator(tmp_path)
    coordinator.trigger()
    context.active_organization = SimpleNamespace(id=2)
    coordinator.organization_changed(2)
    assert workers[0].interrupted
    workers[0].complete()
    app.processEvents()
    assert len(workers) == 2
    assert coordinator._worker_organization_id == 2
    workers[1].complete()


def test_document_controller_has_no_enterprise_worker_or_dialog_imports():
    source = inspect.getsource(DocumentController)
    assert "TransportWorker" not in source
    assert "DocumentRequestsDialog" not in source
    assert "OrganizationTransportDialog" not in source
