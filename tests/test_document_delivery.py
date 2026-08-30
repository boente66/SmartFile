from __future__ import annotations

import io
import http.client
import json
import os
import socket
from dataclasses import replace
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import fitz
from PyQt6.QtCore import QBuffer, QByteArray, Qt
from PyQt6.QtGui import QImage

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.auth.session_context import SessionContext
from app.coordinators.delivery_coordinator import DeliveryCoordinator
from app.controllers.document_delivery_controller import DocumentDeliveryController
from app.delivery.delivery_http_client import DeliveryHttpClient
from app.delivery.delivery_http_server import DeliveryHttpServer
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION
from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.document_delivery_entity import (
    DocumentDeliveryEntity, DocumentDeliveryItemEntity,
)
from app.entities.user_entity import UserEntity
from app.errors.delivery_exceptions import (
    DeliveryIntegrityError,
    DeliveryNetworkError,
    DeliveryValidationError,
)
from app.models.registration_request import RegistrationRequest
from app.models.user_model import UserModel
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.delivery_basket_service import DeliveryBasketService
from app.services.document_delivery_service import DocumentDeliveryService
from app.services.document_request_service import DocumentRequestService
from app.services.document_service import DocumentService
from app.services.organization_feature_service import OrganizationFeatureService


def _installation(root: Path):
    database = Database(str(root / "smartfile.db"))
    context = SessionContext()
    AuthService(database, context).register_first_user(RegistrationRequest(
        display_name="Administrador", username="admin", email="admin@example.com",
        password="Senha#Segura1", password_confirmation="Senha#Segura1",
        template_code="BUSINESS", organization_name="Empresa",
    ))
    policy = OrganizationFeatureService(database, context)
    enabled = set(policy.for_organization(context.active_organization).codes)
    policy.update_enabled_features(
        context.active_organization, enabled | {"document_requests", "deadline_timers"},
    )
    now = datetime.now(timezone.utc).isoformat()
    worker = UserRepository(database=database).create(UserEntity(
        username="responsavel", display_name="Responsável", password_hash="test-only",
        created_at=now, updated_at=now,
    ))
    membership = OrganizationMemberRepository(database=database).create(
        OrganizationMemberEntity(
            organization_id=context.active_organization.id, user_id=worker.id,
            role="EDITOR", created_at=now, updated_at=now,
        )
    )
    documents = DocumentService(database=database)
    return database, context, documents, worker, membership


def _as_worker(context, worker, membership):
    context.current_user = UserModel.from_entity(worker)
    context.memberships.append(membership)
    context.set_active_organization(context.active_organization)


def _source(root: Path, name: str, content: bytes) -> Path:
    path = root / name
    path.write_bytes(content)
    return path


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _signature_png() -> bytes:
    image = QImage(180, 60, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for x in range(20, 160):
        image.setPixelColor(x, 30, Qt.GlobalColor.black)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def _identity_response(port: int) -> tuple[int, dict]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        connection.request("GET", "/api/v1/identity")
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode())
    finally:
        connection.close()


def test_current_schema_and_instance_uuid_survives_ip_change(tmp_path: Path, monkeypatch):
    database, context, _documents, _worker, _membership = _installation(tmp_path)
    version = database.connect().execute("PRAGMA user_version").fetchone()[0]
    assert version == CURRENT_SCHEMA_VERSION == 22
    service = DocumentDeliveryService(database, context)
    monkeypatch.setattr(service.instances, "current_ip", lambda: "192.168.1.10")
    first = service.instances.local(context.active_organization.id)
    monkeypatch.setattr(service.instances, "current_ip", lambda: "192.168.1.99")
    second = service.instances.local(context.active_organization.id)
    assert first.instance_id == second.instance_id
    assert second.current_ip == "192.168.1.99"


def test_public_identity_endpoint_validates_uuid_and_protocol(tmp_path: Path):
    database, context, documents, _worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context, documents)
    coordinator = DeliveryCoordinator(service, context)
    port = coordinator.start(
        context.active_organization.id, "127.0.0.1", 0, background=False,
    )
    try:
        local = service.instances.local(context.active_organization.id)
        payload = DeliveryHttpClient(timeout=2).identity(
            "127.0.0.1", port, expected_instance_id=local.instance_id,
        )
        assert payload == {
            "instance_id": local.instance_id,
            "device_name": local.device_name,
            "protocol_version": DELIVERY_PROTOCOL_VERSION,
        }
        with pytest.raises(Exception, match="identidade retornada"):
            DeliveryHttpClient(timeout=2).identity(
                "127.0.0.1", port, expected_instance_id="SF-wrong",
            )
    finally:
        coordinator.stop()


def test_identity_without_active_organization_returns_structured_conflict(tmp_path: Path):
    database, context, documents, _worker, _membership = _installation(tmp_path)
    context.active_organization = None
    server = DeliveryHttpServer(
        "127.0.0.1", 0, DocumentDeliveryService(database, context, documents)
    )
    port = server.start()
    try:
        status, payload = _identity_response(port)
        assert status == 409
        assert payload == {
            "error": "organization_context_unavailable",
            "message": "Nenhuma organização ativa está disponível.",
        }
    finally:
        server.stop()


def test_identity_unexpected_error_returns_safe_internal_error(tmp_path: Path, monkeypatch):
    database, context, documents, _worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context, documents)
    monkeypatch.setattr(
        service, "identity_payload",
        lambda: (_ for _ in ()).throw(RuntimeError("/tmp/secret token traceback")),
    )
    server = DeliveryHttpServer("127.0.0.1", 0, service)
    port = server.start()
    try:
        status, payload = _identity_response(port)
        assert status == 500
        assert payload == {
            "error": "internal_error",
            "message": "Não foi possível consultar a identidade da instalação.",
        }
        assert "secret" not in json.dumps(payload)
        assert "traceback" not in json.dumps(payload).casefold()
    finally:
        server.stop()


def test_migration_17_preserves_legacy_requests(tmp_path: Path):
    path = tmp_path / "legacy.db"
    database, context, _documents, worker, _membership = _installation(tmp_path)
    request = DocumentRequestService(database, context).create(
        context.active_organization.id, "Documento legado", assigned_to_user_id=worker.id,
    )
    connection = database.connect()
    connection.execute("PRAGMA foreign_keys=OFF")
    for table in ("delivery_history", "document_delivery_items", "document_deliveries", "document_request_documents", "smartfile_instances"):
        connection.execute(f"DROP TABLE {table}")
    connection.execute("ALTER TABLE document_requests RENAME TO document_requests_v18")
    connection.execute("""CREATE TABLE document_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL,
        title TEXT NOT NULL, description TEXT, requested_by_user_id INTEGER,
        assigned_to_user_id INTEGER, status TEXT NOT NULL DEFAULT 'OPEN', due_at TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL, completed_at TEXT
    )""")
    connection.execute("""INSERT INTO document_requests
        (id,organization_id,title,description,requested_by_user_id,assigned_to_user_id,status,due_at,created_at,updated_at,completed_at)
        SELECT id,organization_id,title,description,requested_by_user_id,assigned_to_user_id,status,due_at,created_at,updated_at,completed_at
        FROM document_requests_v18""")
    connection.execute("DROP TABLE document_requests_v18")
    connection.execute("PRAGMA user_version=17"); connection.execute("PRAGMA foreign_keys=ON")
    database.close()
    migrated = Database(str(tmp_path / "smartfile.db"))
    row = migrated.fetch_one("SELECT * FROM document_requests WHERE id=?", (request.id,))
    assert row["title"] == "Documento legado"
    from uuid import UUID
    assert str(UUID(row["request_uuid"])) == row["request_uuid"]
    assert migrated.connect().execute("PRAGMA user_version").fetchone()[0] == 22


def test_migration_19_adds_receipts_without_losing_deliveries(tmp_path: Path):
    database, context, _documents, worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context)
    delivery = service.deliveries.create(DocumentDeliveryEntity(
        delivery_uuid="9c9bf0fd-c8c4-462a-81aa-1d4fcf0cd3a8",
        protocol_number="SF-20260824-000099-ABCD",
        organization_id=context.active_organization.id,
        sender_user_id=worker.id,
        recipient_user_id=context.current_user.id,
        sender_instance_id="SF-sender", recipient_instance_id="SF-local",
        recipient_host="127.0.0.1", direction="INCOMING",
        status="DELIVERED", created_at=service._now(),
    ))
    connection = database.connect()
    connection.execute("DROP TABLE delivery_acknowledgement_receipts")
    connection.execute("PRAGMA user_version=19")
    database.close()

    migrated = Database(str(tmp_path / "smartfile.db"))

    assert migrated.fetch_one("PRAGMA user_version")[0] == 22
    assert migrated.fetch_one(
        "SELECT protocol_number FROM document_deliveries WHERE id=?", (delivery.id,)
    )["protocol_number"] == delivery.protocol_number
    assert migrated.fetch_one(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name='delivery_acknowledgement_receipts'"
    ) is not None


def test_receipt_pdf_is_atomic_and_original_remains_unchanged(
    tmp_path: Path, monkeypatch,
):
    original_open = Path.open
    temporary_open_modes = []

    def tracked_open(path, mode="r", *args, **kwargs):
        if path.name.endswith(".part.pdf"):
            temporary_open_modes.append(mode)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracked_open)
    database, context, _documents, worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context)
    now = service._now()
    delivery = service.deliveries.create(DocumentDeliveryEntity(
        delivery_uuid="58cab411-eae4-4308-b008-0fe7e4300b64",
        protocol_number="SF-20260824-000100-ABCD",
        organization_id=context.active_organization.id,
        sender_user_id=worker.id,
        recipient_user_id=context.current_user.id,
        sender_instance_id="SF-sender", recipient_instance_id="SF-local",
        recipient_host="127.0.0.1", direction="INCOMING",
        status="VIEWED", created_at=now, delivered_at=now, viewed_at=now,
    ))
    original = _source(tmp_path, "received.pdf", b"immutable-original")
    checksum = service._checksum(original)
    service.items.create(DocumentDeliveryItemEntity(
        item_uuid="item-receipt", delivery_id=delivery.id,
        logical_name="received.pdf", size=original.stat().st_size,
        sha256=checksum, transfer_status="VERIFIED",
        received_path=str(original), received_at=now,
    ))

    receipt = service.create_acknowledgement_receipt(
        delivery.id, context.current_user.id, _signature_png(), "DRAWN"
    )

    assert original.read_bytes() == b"immutable-original"
    assert service._checksum(original) == checksum
    assert receipt.status == "QUEUED"
    assert Path(receipt.pdf_path).is_file()
    assert service._checksum(Path(receipt.pdf_path)) == receipt.sha256
    assert "r+b" in temporary_open_modes
    assert list(Path(receipt.pdf_path).parent.glob("*.part*")) == []
    with fitz.open(receipt.pdf_path) as proof:
        text = "\n".join(page.get_text() for page in proof)
    assert delivery.protocol_number in text
    assert receipt.receipt_uuid in text
    assert checksum in text
    assert "Responsável" in text and "Administrador" in text
    assert "Assinatura visual" in text
    with pytest.raises(DeliveryValidationError):
        service.create_acknowledgement_receipt(
            delivery.id, context.current_user.id, _signature_png(), "DRAWN"
        )


def test_receipt_metadata_is_idempotent_and_bad_checksum_removes_partial(tmp_path: Path):
    database, context, _documents, worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context)
    delivery = service.deliveries.create(DocumentDeliveryEntity(
        delivery_uuid="0da7c480-603d-4439-b6c2-9ea7bf025403",
        protocol_number="SF-20260824-000101-ABCD",
        organization_id=context.active_organization.id,
        sender_user_id=context.current_user.id, recipient_user_id=worker.id,
        sender_instance_id="SF-local", recipient_instance_id="SF-recipient",
        recipient_host="127.0.0.1", direction="OUTGOING",
        status="VIEWED", created_at=service._now(),
    ))
    content = b"not-the-declared-pdf"
    payload = {
        "receipt_uuid": "6d4d699e-bfd8-4bff-9ed3-c1cd4b364ffe",
        "protocol_number": delivery.protocol_number,
        "signer_username": worker.username,
        "signature_method": "IMPORTED_IMAGE",
        "size": len(content),
        "sha256": "0" * 64,
        "created_at": service._now(),
    }

    first = service.receive_receipt_metadata(delivery.protocol_number, payload)
    again = service.receive_receipt_metadata(delivery.protocol_number, payload)

    assert first.id == again.id
    with pytest.raises(DeliveryIntegrityError):
        service.receive_receipt_content(
            delivery.protocol_number, first.receipt_uuid,
            io.BytesIO(content), len(content),
        )
    receipt_root = (
        database.paths.data_dir / "delivery_receipts" / delivery.protocol_number
    )
    assert list(receipt_root.glob("*.part")) == []
    changed = dict(payload, sha256="1" * 64)
    with pytest.raises(DeliveryValidationError):
        service.receive_receipt_metadata(delivery.protocol_number, changed)


def test_received_pdf_uses_internal_viewer_and_marks_viewed_only_after_display(tmp_path: Path):
    path = _source(tmp_path, "received.pdf", b"pdf-placeholder")
    delivery = SimpleNamespace(
        id=9, protocol_number="SF-20260824-000102-ABCD",
        status="DELIVERED", sender_user_id=2, recipient_user_id=1,
    )
    item = SimpleNamespace(
        logical_name="received.pdf", received_path=str(path),
    )
    marked = []

    class Viewer:
        def open_document(self, opened_path, context):
            self.path = opened_path
            self.context = context

    viewer = Viewer()
    controller = DocumentDeliveryController.__new__(DocumentDeliveryController)
    controller.pdf_viewer = viewer
    controller._viewer_delivery_id = None
    controller.context = SimpleNamespace(
        current_user=SimpleNamespace(id=1),
        has_permission=lambda permission: permission == "delivery.acknowledge",
    )
    controller.service = SimpleNamespace(
        deliveries=SimpleNamespace(find_by_id=lambda _id: delivery),
        items=SimpleNamespace(list_by_delivery=lambda _id: [item]),
        users=SimpleNamespace(
            find_by_id=lambda _id: SimpleNamespace(display_name="Remetente")
        ),
        receipts=SimpleNamespace(find_by_delivery=lambda _id: None),
        mark_viewed=lambda protocol, user_id: marked.append((protocol, user_id)),
    )
    controller.refresh = lambda: None
    controller._error = pytest.fail

    controller.view_delivery(delivery.id)

    assert viewer.path == str(path)
    assert viewer.context.kind == "DELIVERY_RECEIVED"
    assert marked == []
    controller._viewer_displayed(str(path))
    assert marked == [(delivery.protocol_number, 1)]


def test_request_transitions_basket_and_unique_protocol(tmp_path: Path):
    database, context, documents, worker, _membership = _installation(tmp_path)
    requests = DocumentRequestService(database, context)
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    request = requests.create(context.active_organization.id, "Contrato assinado", assigned_to_user_id=worker.id, due_at=due)
    requests.set_status(context.active_organization.id, request.id, "IN_PROGRESS")
    with pytest.raises(ValueError, match="Transição inválida"):
        requests.set_status(context.active_organization.id, request.id, "DELIVERED")
    requests.set_status(context.active_organization.id, request.id, "ATTENDED")

    document = documents.import_document(str(_source(tmp_path, "contrato.pdf", b"pdf-content")), sync_cloud=False)
    basket = DeliveryBasketService(documents, context)
    basket.begin(request_id=request.id, recipient_user_id=context.current_user.id)
    basket.add_document(document.id); basket.add_document(document.id)
    assert len(basket.basket.items) == 1 and basket.basket.total_size == len(b"pdf-content")
    basket.remove_document(document.id)
    assert not basket.basket.items

    delivery_service = DocumentDeliveryService(database, context, documents)
    local = delivery_service.instances.local(context.active_organization.id)
    peer = delivery_service.instances.register_peer(
        context.active_organization.id, "SF-00000000-0000-0000-0000-000000000002",
        "Remoto", "127.0.0.1", 54321, context.current_user.id,
    )
    basket.add_document(document.id)
    first = delivery_service.create(context.active_organization.id, basket.basket, peer.instance_id)
    basket.begin(recipient_user_id=context.current_user.id); basket.add_document(document.id)
    second = delivery_service.create(context.active_organization.id, basket.basket, peer.instance_id)
    assert first.protocol_number != second.protocol_number
    assert first.sender_instance_id == local.instance_id


def test_receive_rejects_path_traversal_and_bad_checksum(tmp_path: Path):
    database, context, documents, worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context, documents)
    local = service.instances.local(context.active_organization.id)
    peer = service.instances.register_peer(
        context.active_organization.id, "SF-00000000-0000-0000-0000-000000000009",
        "Origem", "127.0.0.1", 54322, worker.id,
    )
    base = {
        "delivery_uuid": "00000000-0000-0000-0000-000000000099",
        "protocol_number": "SF-20260815-000001-A1B2",
        "request_uuid": None,
        "sender_username": "responsavel", "recipient_username": "admin",
        "sender_instance_id": peer.instance_id, "recipient_instance_id": local.instance_id,
        "message": None,
        "items": [{"item_uuid": "item-1", "logical_name": "../../segredo.pdf", "size": 4, "sha256": "0" * 64}],
    }
    with pytest.raises(DeliveryValidationError, match="Nome de documento"):
        service.receive_metadata(base)
    base["items"][0]["logical_name"] = "seguro.pdf"
    base["items"][0]["sha256"] = "a" * 64
    service.receive_metadata(base)
    with pytest.raises(DeliveryIntegrityError, match="SHA-256"):
        service.receive_item(base["protocol_number"], "item-1", io.BytesIO(b"data"), 4)
    assert not list((database.paths.data_dir / "delivery_inbox" / base["protocol_number"]).glob("*.part"))


def test_receive_streams_in_bounded_chunks(tmp_path: Path):
    database, context, documents, worker, _membership = _installation(tmp_path)
    service = DocumentDeliveryService(database, context, documents)
    local = service.instances.local(context.active_organization.id)
    peer = service.instances.register_peer(
        context.active_organization.id, "SF-00000000-0000-0000-0000-000000000019",
        "Origem", "127.0.0.1", 54323, worker.id,
    )
    content = b"x" * (service.CHUNK_SIZE * 2 + 137)
    import hashlib
    payload = {
        "delivery_uuid": "00000000-0000-0000-0000-000000000199",
        "protocol_number": "SF-20260815-000002-A1B2", "request_uuid": None,
        "sender_username": "responsavel", "recipient_username": "admin",
        "sender_instance_id": peer.instance_id, "recipient_instance_id": local.instance_id,
        "message": None, "items": [{"item_uuid": "item-stream", "logical_name": "grande.pdf", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}],
    }
    service.receive_metadata(payload)
    class GuardedStream(io.BytesIO):
        largest = 0
        def read(self, size=-1):
            self.largest = max(self.largest, size)
            assert size <= service.CHUNK_SIZE
            return super().read(size)
    stream = GuardedStream(content)
    output = service.receive_item(payload["protocol_number"], "item-stream", stream, len(content))
    assert output.read_bytes() == content and stream.largest == service.CHUNK_SIZE


def test_two_instances_request_delivery_view_and_acknowledge(tmp_path: Path):
    db_a, context_a, documents_a, worker_a, _member_a = _installation(tmp_path / "a")
    db_b, context_b, documents_b, worker_b, member_b = _installation(tmp_path / "b")
    _as_worker(context_b, worker_b, member_b)

    service_a = DocumentDeliveryService(db_a, context_a, documents_a)
    service_b = DocumentDeliveryService(db_b, context_b, documents_b)
    coordinator_a = DeliveryCoordinator(service_a, context_a)
    coordinator_b = DeliveryCoordinator(service_b, context_b)
    port_a = coordinator_a.start(context_a.active_organization.id, "127.0.0.1", 0, background=False)
    port_b = coordinator_b.start(context_b.active_organization.id, "127.0.0.1", 0, background=False)
    try:
        local_a = service_a.instances.local(context_a.active_organization.id)
        local_b = service_b.instances.local(context_b.active_organization.id)
        service_a.instances.register_peer(context_a.active_organization.id, local_b.instance_id, "Zorin", "127.0.0.1", port_b, worker_a.id)
        service_b.instances.register_peer(context_b.active_organization.id, local_a.instance_id, "Mint", "127.0.0.1", port_a, context_b.memberships[0].user_id)

        requests_a = DocumentRequestService(db_a, context_a)
        request_a = requests_a.create(context_a.active_organization.id, "Nota fiscal", assigned_to_user_id=worker_a.id)
        peer_b = service_a.instances.repository.find_by_instance_id(local_b.instance_id)
        coordinator_a.send_request(request_a.id, peer_b)
        request_b = service_b.requests.find_by_uuid(request_a.request_uuid)
        assert request_b and request_b.assigned_to_user_id == worker_b.id

        requests_b = DocumentRequestService(db_b, context_b)
        requests_b.set_status(context_b.active_organization.id, request_b.id, "IN_PROGRESS")
        document = documents_b.import_document(str(_source(tmp_path / "b", "nota.pdf", b"first-document")), sync_cloud=False)
        requests_b.link_document(context_b.active_organization.id, request_b.id, document.id)
        requests_b.set_status(context_b.active_organization.id, request_b.id, "ATTENDED")
        basket = DeliveryBasketService(documents_b, context_b)
        basket.begin(request_id=request_b.id, recipient_user_id=context_b.memberships[0].user_id)
        basket.add_document(document.id)
        peer_a = service_b.instances.repository.find_by_instance_id(local_a.instance_id)
        delivery_b = service_b.create(context_b.active_organization.id, basket.basket, peer_a.instance_id, "Conforme solicitado")
        service_b.queue(delivery_b.id)
        coordinator_b.send_once(delivery_b.id)

        incoming_a = service_a.deliveries.find_by_protocol(delivery_b.protocol_number)
        assert incoming_a and incoming_a.status == "DELIVERED"
        service_a.mark_viewed(incoming_a.protocol_number, context_a.current_user.id)
        coordinator_b.refresh_remote(delivery_b.id)
        assert service_b.deliveries.find_by_id(delivery_b.id).status == "VIEWED"
        receipt = service_a.create_acknowledgement_receipt(
            incoming_a.id, context_a.current_user.id, _signature_png(), "DRAWN"
        )
        coordinator_a.send_receipt_once(receipt.id)
        assert service_b.deliveries.find_by_id(delivery_b.id).status == "ACKNOWLEDGED"
        assert service_b.receipts.find_by_delivery(delivery_b.id).status == "VERIFIED"
        assert service_b.requests.find_by_id(request_b.id, request_b.organization_id).status == "COMPLETED"
        assert service_a.requests.find_by_id(request_a.id, request_a.organization_id).status == "COMPLETED"
    finally:
        coordinator_b.stop(); coordinator_a.stop()


def test_offline_delivery_remains_queued_then_retries(tmp_path: Path):
    db_a, context_a, documents_a, worker_a, member_a = _installation(tmp_path / "a")
    db_b, context_b, documents_b, worker_b, member_b = _installation(tmp_path / "b")
    _as_worker(context_a, worker_a, member_a)
    _as_worker(context_b, worker_b, member_b)
    service_a = DocumentDeliveryService(db_a, context_a, documents_a)
    service_b = DocumentDeliveryService(db_b, context_b, documents_b)
    port_b = _free_port()
    local_a = service_a.instances.local(context_a.active_organization.id)
    local_b = service_b.instances.local(context_b.active_organization.id, port_b)
    peer_b = service_a.instances.register_peer(context_a.active_organization.id, local_b.instance_id, "Offline", "127.0.0.1", port_b, worker_a.id)
    service_b.instances.register_peer(context_b.active_organization.id, local_a.instance_id, "Origem", "127.0.0.1", _free_port(), worker_b.id)
    document = documents_a.import_document(str(_source(tmp_path / "a", "offline.pdf", b"offline-data")), sync_cloud=False)
    basket = DeliveryBasketService(documents_a, context_a); basket.begin(recipient_user_id=worker_a.id); basket.add_document(document.id)
    delivery = service_a.create(context_a.active_organization.id, basket.basket, peer_b.instance_id)
    coordinator_a = DeliveryCoordinator(service_a, context_a)
    with pytest.raises(Exception): coordinator_a.send_once(delivery.id)
    assert service_a.deliveries.find_by_id(delivery.id).status == "QUEUED"
    coordinator_b = DeliveryCoordinator(service_b, context_b)
    try:
        coordinator_b.start(context_b.active_organization.id, "127.0.0.1", port_b, background=False)
        service_a.deliveries.update(delivery.id, next_attempt_at=service_a._now())
        coordinator_a.process_pending_sync()
        assert service_a.deliveries.find_by_id(delivery.id).status == "DELIVERED"
    finally:
        coordinator_b.stop()


def test_offline_receipt_is_deferred_without_expected_network_traceback(
    caplog, monkeypatch,
):
    receipt = SimpleNamespace(id=7, receipt_uuid="receipt-offline")
    service = SimpleNamespace(
        notification_callback=None,
        receipts=SimpleNamespace(pending=lambda _now: [receipt]),
    )
    coordinator = DeliveryCoordinator(service)

    def unavailable(_receipt_id):
        raise DeliveryNetworkError(
            "Não foi possível enviar o comprovante: rede indisponível"
        )

    monkeypatch.setattr(coordinator, "send_receipt_once", unavailable)
    with caplog.at_level("INFO"):
        coordinator.process_pending_receipts()
        coordinator.process_pending_receipts()

    records = [
        record for record in caplog.records
        if record.getMessage().startswith("delivery.network.deferred")
    ]
    assert len(records) == 1
    assert records[0].exc_info is None
    assert "permanece na fila" in coordinator._last_cycle_message
