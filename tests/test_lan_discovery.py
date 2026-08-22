from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import os
import threading
import time

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPushButton
from zeroconf import ServiceStateChange

from app.database.database import Database
from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.models.lan_discovery import DiscoveredSmartFile
from app.services.lan_device_discovery_service import LanDeviceDiscoveryService
from app.services.smartfile_instance_service import SmartFileInstanceService
from app.views.delivery_network_dialog import DeliveryNetworkDialog
from app.workers.lan_discovery_worker import LanDiscoveryWorker
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION


_APPLICATION = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


class _Info:
    port = 8765
    properties = {
        b"instance_id": b"SF-remote-123",
        b"device_name": b"Notebook Financeiro",
        b"protocol_version": DELIVERY_PROTOCOL_VERSION.encode("ascii"),
        b"token": b"must-not-be-read",
    }

    @staticmethod
    def parsed_scoped_addresses():
        return ["192.168.1.22"]


class _Zeroconf:
    def __init__(self, info=None):
        self.info = info or _Info()
        self.closed = False

    def get_service_info(self, _service_type, _name, timeout):
        assert timeout <= 700
        return self.info

    def close(self):
        self.closed = True


class _Browser:
    def __init__(self, client, service_type, handlers):
        self.cancelled = False
        handlers[0](client, service_type, "remote._smartfile._tcp.local.", ServiceStateChange.Added)

    def cancel(self):
        self.cancelled = True


class _EmptyBrowser:
    def __init__(self, _client, _service_type, handlers):
        self.handlers = handlers
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


def test_discovery_normalizes_only_minimal_safe_metadata() -> None:
    device = LanDeviceDiscoveryService.normalize_service_info("service", _Info())
    assert device == DiscoveredSmartFile(
        instance_id="SF-remote-123", device_name="Notebook Financeiro",
        host="192.168.1.22", port=8765,
        protocol_version=DELIVERY_PROTOCOL_VERSION,
        service_name="service",
    )
    assert not hasattr(device, "token")


@pytest.mark.parametrize(
    "change",
    [
        {"properties": {b"instance_id": b"invalid"}},
        {"port": 80},
        {"addresses": ["224.0.0.1"]},
    ],
)
def test_invalid_discovery_records_are_ignored(change) -> None:
    info = _Info()
    info = SimpleNamespace(
        port=change.get("port", info.port),
        properties=change.get("properties", info.properties),
        parsed_scoped_addresses=lambda: change.get("addresses", ["192.168.1.22"]),
    )
    assert LanDeviceDiscoveryService.normalize_service_info("service", info) is None


def test_discovery_honors_timeout_and_closes_runtime() -> None:
    client = _Zeroconf()
    service = LanDeviceDiscoveryService(
        zeroconf_factory=lambda: client, browser_factory=_Browser,
    )
    devices = service.discover(0.1)
    assert [item.instance_id for item in devices] == ["SF-remote-123"]
    assert client.closed


def test_discovery_can_be_cancelled_without_persisting_or_hanging() -> None:
    client = _Zeroconf()
    service = LanDeviceDiscoveryService(
        zeroconf_factory=lambda: client, browser_factory=_Browser,
    )
    devices = service.discover(5, cancelled=lambda: True)
    assert len(devices) == 1
    assert client.closed


def test_discovery_with_no_response_finishes_empty() -> None:
    client = _Zeroconf()
    service = LanDeviceDiscoveryService(
        zeroconf_factory=lambda: client, browser_factory=_EmptyBrowser,
    )
    assert service.discover(0.1) == []
    assert client.closed


def _instance_service(tmp_path):
    database = Database(str(tmp_path / "lan.db"))
    organization_id = database.execute_query(
        "INSERT INTO organizations(name,slug,created_at,updated_at,is_default) VALUES(?,?,?,?,1)",
        ("Empresa", "empresa", "now", "now"),
    ).lastrowid
    return database, organization_id, SmartFileInstanceService(database)


def test_discovery_updates_ip_only_for_previously_authorized_uuid(tmp_path) -> None:
    _database, organization_id, service = _instance_service(tmp_path)
    authorized = SmartFileInstanceEntity(
        instance_id="SF-authorized", organization_id=organization_id,
        device_name="Notebook", current_ip="192.168.1.5", http_port=8765,
        is_local=False, created_at="now",
    )
    service.repository.save(authorized)
    candidate = DiscoveredSmartFile(
        "SF-authorized", "Notebook Novo", "192.168.1.88", 9000,
        DELIVERY_PROTOCOL_VERSION, "service",
    )
    updated = service.apply_discovery(organization_id, candidate)
    assert updated.current_ip == "192.168.1.88"
    assert updated.http_port == 9000

    unknown = replace(candidate, instance_id="SF-not-authorized")
    assert service.apply_discovery(organization_id, unknown) is None
    assert service.repository.find_by_instance_id("SF-not-authorized") is None


def test_same_ip_with_different_uuid_does_not_replace_authorized_peer(tmp_path) -> None:
    _database, organization_id, service = _instance_service(tmp_path)
    service.repository.save(SmartFileInstanceEntity(
        instance_id="SF-authorized", organization_id=organization_id,
        device_name="Notebook", current_ip="192.168.1.5", http_port=8765,
        is_local=False, created_at="now",
    ))
    impostor = DiscoveredSmartFile(
        "SF-other", "Outro", "192.168.1.5", 8765,
        DELIVERY_PROTOCOL_VERSION, "service",
    )
    assert service.apply_discovery(organization_id, impostor) is None
    assert service.repository.find_by_instance_id("SF-authorized").device_name == "Notebook"


def test_network_dialog_ignores_self_keeps_manual_fallback_and_incompatible_state() -> None:
    _app()
    local = SmartFileInstanceEntity(
        instance_id="SF-local", organization_id=1, device_name="LeoPc",
        current_ip="192.168.1.10", http_port=8765, is_local=True,
    )
    dialog = DeliveryNetworkDialog(local, [], [])
    dialog.set_discovered([
        DiscoveredSmartFile(
            "SF-local", "LeoPc", "192.168.1.10", 8765,
            DELIVERY_PROTOCOL_VERSION, "self",
        ),
        DiscoveredSmartFile("SF-new", "Zorin", "192.168.1.20", 8765, "2", "other"),
    ])
    buttons = dialog.findChildren(QPushButton)
    authorize = next(button for button in buttons if button.text() == "Autorizar")
    assert not authorize.isEnabled()
    assert dialog.manual_group.isCheckable() and not dialog.manual_group.isChecked()
    dialog.manual_group.setChecked(True)
    assert dialog.peer_id.parentWidget().isVisibleTo(dialog)


def test_discovery_worker_runs_outside_ui_thread_and_can_be_interrupted() -> None:
    _app()
    started = threading.Event()

    class SlowService:
        @staticmethod
        def discover(_timeout, *, cancelled):
            started.set()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not cancelled():
                time.sleep(0.01)
            return []

    worker = LanDiscoveryWorker(SlowService(), timeout=2)
    worker.start()
    assert started.wait(0.5)
    assert worker.isRunning()
    worker.requestInterruption()
    assert worker.wait(1000)


def test_dialog_can_close_while_discovery_worker_is_active() -> None:
    _app()

    class SlowService:
        @staticmethod
        def discover(_timeout, *, cancelled):
            while not cancelled():
                time.sleep(0.01)
            return []

    local = SmartFileInstanceEntity(
        instance_id="SF-local", organization_id=1, device_name="LeoPc",
        current_ip="192.168.1.10", http_port=8765, is_local=True,
    )
    dialog = DeliveryNetworkDialog(local, [], [])
    worker = LanDiscoveryWorker(SlowService(), timeout=2)
    worker.start()
    dialog.close()
    worker.requestInterruption()
    assert worker.wait(1000)
