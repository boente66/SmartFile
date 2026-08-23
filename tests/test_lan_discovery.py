from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import os
import threading
import time

import pytest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFrame, QPushButton
from zeroconf import ServiceStateChange

from app.controllers.document_delivery_controller import DocumentDeliveryController
from app.database.database import Database
from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.models.lan_discovery import DiscoveredSmartFile
from app.services.lan_device_discovery_service import (
    LanDeviceDiscoveryService, LanDiscoveryError,
)
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


class _KeywordUpdatedBrowser:
    def __init__(self, client, service_type, handlers):
        self.cancelled = False
        handlers[0](
            zeroconf=client,
            service_type=service_type,
            name="remote._smartfile._tcp.local.",
            state_change=ServiceStateChange.Updated,
        )

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


def test_discovery_accepts_real_zeroconf_keyword_callback_and_updated_state() -> None:
    client = _Zeroconf()
    service = LanDeviceDiscoveryService(
        zeroconf_factory=lambda: client, browser_factory=_KeywordUpdatedBrowser,
    )
    devices = service.discover(0.1)
    assert [item.instance_id for item in devices] == ["SF-remote-123"]
    assert client.closed


def test_discovery_callback_failure_reaches_service_instead_of_dying_silently() -> None:
    class BrokenClient(_Zeroconf):
        def get_service_info(self, *_args, **_kwargs):
            raise RuntimeError("resolver defect")

    client = BrokenClient()
    service = LanDeviceDiscoveryService(
        zeroconf_factory=lambda: client, browser_factory=_KeywordUpdatedBrowser,
    )
    with pytest.raises(LanDiscoveryError, match="anúncio mDNS"):
        service.discover(0.1)
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


def test_discovery_updates_ip_only_after_http_identity_validation(tmp_path) -> None:
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
    assert service.apply_discovery(organization_id, candidate) is None
    unchanged = service.repository.find_by_instance_id("SF-authorized")
    assert unchanged.current_ip == "192.168.1.5"
    assert unchanged.http_port == 8765

    updated = service.apply_discovery(
        organization_id, candidate,
        identity={
            "instance_id": "SF-authorized",
            "protocol_version": DELIVERY_PROTOCOL_VERSION,
        },
    )
    assert updated.current_ip == "192.168.1.88"
    assert updated.http_port == 9000

    unknown = replace(candidate, instance_id="SF-not-authorized")
    assert service.apply_discovery(organization_id, unknown) is None
    assert service.repository.find_by_instance_id("SF-not-authorized") is None


def test_verified_connection_can_persist_candidate_endpoint(tmp_path, monkeypatch) -> None:
    _database, organization_id, service = _instance_service(tmp_path)
    service.repository.save(SmartFileInstanceEntity(
        instance_id="SF-authorized", organization_id=organization_id,
        device_name="Notebook", current_ip="192.168.1.5", http_port=8765,
        is_local=False, created_at="now",
    ))
    monkeypatch.setattr(
        "app.delivery.delivery_http_client.DeliveryHttpClient.identity",
        lambda _client, _host, _port, *, expected_instance_id: {
            "instance_id": expected_instance_id,
            "protocol_version": DELIVERY_PROTOCOL_VERSION,
        },
    )
    candidate = SmartFileInstanceEntity(
        instance_id="SF-authorized", organization_id=organization_id,
        device_name="Notebook novo", current_ip="192.168.1.99", http_port=9000,
        is_local=False,
    )
    service.test_connection(candidate)
    persisted = service.repository.find_by_instance_id("SF-authorized")
    assert persisted.current_ip == "192.168.1.99"
    assert persisted.http_port == 9000


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


def test_network_dialog_refresh_keeps_single_non_overlapping_empty_state() -> None:
    app = _app()
    local = SmartFileInstanceEntity(
        instance_id="SF-local", organization_id=1, device_name="LeoPc",
        current_ip="192.168.1.10", http_port=8765, is_local=True,
    )
    dialog = DeliveryNetworkDialog(local, [], [])
    dialog.show()
    for _ in range(3):
        dialog.set_peers([])
        dialog.set_discovered([])
    app.processEvents()

    assert dialog.discovered_container.count() == 1
    cards = dialog.findChildren(QFrame, "networkDeviceCard")
    assert len(cards) == 2  # esta instalação + estado vazio
    local_card = next(card for card in cards if card.property("cardRole") == "local")
    empty_card = next(card for card in cards if card.property("cardRole") == "empty")
    assert local_card.isVisibleTo(dialog)
    assert empty_card.isVisibleTo(dialog)
    assert not local_card.geometry().intersects(empty_card.geometry())
    dialog.close()


def test_manual_form_rejects_invalid_identity_without_emitting_slot() -> None:
    _app()
    local = SmartFileInstanceEntity(
        instance_id="SF-local", organization_id=1, device_name="LeoPc",
        current_ip="192.168.1.10", http_port=8765, is_local=True,
    )
    member = SimpleNamespace(id=7, display_name="Financeiro")
    dialog = DeliveryNetworkDialog(local, [], [member])
    emitted = []
    dialog.save_peer_requested.connect(emitted.append)
    dialog.peer_id.setText("identidade-invalida")
    dialog.peer_host.setText("192.168.1.20")
    dialog._submit_peer()
    assert emitted == []
    assert "iniciada por SF-" in dialog.discovery_status.text()
    dialog.close()


def test_register_peer_normalizes_identity_and_rejects_invalid_owner(tmp_path) -> None:
    database, organization_id, service = _instance_service(tmp_path)
    user_id = database.execute_query(
        """INSERT INTO users(
               username,display_name,password_hash,created_at,updated_at
           ) VALUES ('peer-owner','Peer Owner','hash','now','now')"""
    ).lastrowid
    database.execute_query(
        """INSERT INTO organization_members(
               organization_id,user_id,role,status,created_at,updated_at
           ) VALUES (?,?,'EDITOR','ACTIVE','now','now')""",
        (organization_id, user_id),
    )
    peer = service.register_peer(
        organization_id, "  SF-abc  ", "Notebook", "192.168.1.20", 8765,
        user_id,
    )
    assert peer.instance_id == "SF-abc"
    assert service.repository.find_by_instance_id("SF-abc") is not None
    with pytest.raises(ValueError, match="Identidade"):
        service.register_peer(
            organization_id, "", "Notebook", "192.168.1.20", 8765, user_id,
        )
    with pytest.raises(ValueError, match="Identidade"):
        service.register_peer(
            organization_id, "abc", "Notebook", "192.168.1.20", 8765, user_id,
        )
    with pytest.raises(ValueError, match="membro ativo"):
        service.register_peer(
            organization_id, "SF-other", "Notebook", "192.168.1.20", 8765, 9999,
        )


def test_local_ip_uses_lan_route_without_internet_dependency(monkeypatch) -> None:
    targets = []

    class Probe:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def connect(self, target):
            targets.append(target)

        @staticmethod
        def getsockname():
            return "192.168.50.10", 43210

    monkeypatch.setattr("socket.socket", lambda *_args, **_kwargs: Probe())
    monkeypatch.setattr("socket.getaddrinfo", lambda *_args, **_kwargs: [])
    assert SmartFileInstanceService.current_ip() == "192.168.50.10"
    assert targets == [("224.0.0.251", 5353)]
    assert LanDeviceDiscoveryService._local_ipv4("127.0.0.1") is None


def test_manual_controller_validation_is_reported_without_unhandled_exception() -> None:
    controller = DocumentDeliveryController.__new__(DocumentDeliveryController)

    class Instances:
        class Repository:
            @staticmethod
            def list_peers(_organization_id):
                return []

        repository = Repository()

        @staticmethod
        def register_peer(_organization_id, **_values):
            raise ValueError("Identidade SmartFile inválida.")

    controller.service = SimpleNamespace(instances=Instances())
    messages = []
    dialog = SimpleNamespace(
        set_peers=lambda _peers: None,
        show_connection_result=lambda *_args: None,
        show_form_error=messages.append,
    )
    controller._save_manual_peer(dialog, 1, {
        "instance_id": "invalid", "device_name": "Peer",
        "host": "192.168.1.20", "port": 8765, "owner_user_id": 1,
    })
    assert messages == [
        "SmartFile ID inválido. Use a identificação exibida no outro "
        "SmartFile, iniciada por SF-."
    ]


def test_controller_treats_mdns_endpoint_as_candidate_until_http_validation() -> None:
    controller = DocumentDeliveryController.__new__(DocumentDeliveryController)
    local = SmartFileInstanceEntity(
        instance_id="SF-local", organization_id=1, device_name="Local",
        current_ip="192.168.1.10", http_port=8765, is_local=True,
    )
    authorized = SmartFileInstanceEntity(
        instance_id="SF-authorized", organization_id=1, device_name="Peer antigo",
        owner_user_id=4, current_ip="192.168.1.20", http_port=8765,
        is_local=False,
    )

    class Repository:
        @staticmethod
        def list_peers(_organization_id):
            return [authorized]

    controller.service = SimpleNamespace(
        instances=SimpleNamespace(local=lambda _organization_id: local, repository=Repository())
    )
    started = []
    controller._start_connection_worker = (
        lambda _dialog, candidate, _success: started.append(candidate)
    )
    visible = []
    dialog = SimpleNamespace(
        show_connection_pending=lambda *_args: None,
        set_peers=lambda _peers: None,
        set_discovered=lambda devices: visible.extend(devices),
        set_discovery_state=lambda *_args: None,
    )
    controller.network_dialog = dialog
    devices = [
        DiscoveredSmartFile(
            "SF-authorized", "Peer novo", "192.168.1.99", 9000,
            DELIVERY_PROTOCOL_VERSION, "known",
        ),
        DiscoveredSmartFile(
            "SF-unknown", "Desconhecido", "192.168.1.30", 8765,
            DELIVERY_PROTOCOL_VERSION, "unknown",
        ),
    ]
    controller._discovery_succeeded(dialog, 1, devices)
    assert len(started) == 1
    assert started[0].instance_id == "SF-authorized"
    assert started[0].current_ip == "192.168.1.99"
    assert authorized.current_ip == "192.168.1.20"
    assert [item.instance_id for item in visible] == ["SF-authorized", "SF-unknown"]


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
