from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import CloudAuthResult
from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.errors.cloud_exceptions import CloudAccountOwnershipError
from app.services.document_service import DocumentService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _add_historical_references(service: DocumentService, document_id: int) -> dict[str, int]:
    organization_id = service.active_organization_id
    now = _now()
    request_id = service.database.execute_query(
        """INSERT INTO document_requests(
               request_uuid,organization_id,title,status,created_at,updated_at
           ) VALUES (?,?,?,'COMPLETED',?,?)""",
        ("request-delete-test", organization_id, "Documento histórico", now, now),
    ).lastrowid
    service.database.execute_query(
        """INSERT INTO document_request_documents(
               request_id,document_id,created_at
           ) VALUES (?,?,?)""",
        (request_id, document_id, now),
    )
    delivery_id = service.database.execute_query(
        """INSERT INTO document_deliveries(
               delivery_uuid,protocol_number,organization_id,request_id,
               sender_instance_id,recipient_instance_id,recipient_host,
               recipient_port,direction,status,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "delivery-delete-test", "SF-DELETE-TEST", organization_id, request_id,
            "sender", "recipient", "127.0.0.1", 8765, "OUTGOING",
            "ACKNOWLEDGED", now,
        ),
    ).lastrowid
    item_id = service.database.execute_query(
        """INSERT INTO document_delivery_items(
               item_uuid,delivery_id,document_id,logical_name,size,sha256,
               transfer_status
           ) VALUES (?,?,?,?,?,?,?)""",
        (
            "item-delete-test", delivery_id, document_id, "contrato.pdf", 16,
            "a" * 64, "VERIFIED",
        ),
    ).lastrowid
    receipt_id = service.database.execute_query(
        """INSERT INTO delivery_acknowledgement_receipts(
               receipt_uuid,delivery_id,organization_id,signer_username,
               signature_method,direction,size,sha256,status,created_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            "receipt-delete-test", delivery_id, organization_id, "destinatario",
            "DRAWN", "LOCAL", 32, "b" * 64, "VERIFIED", now,
        ),
    ).lastrowid
    return {"request": request_id, "delivery": delivery_id, "item": item_id, "receipt": receipt_id}


def test_permanent_delete_preserves_historical_snapshots_and_integrity(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    source = tmp_path / "contrato.pdf"
    source.write_bytes(b"historical-pdf")
    document = service.import_document(str(source), sync_cloud=False)
    references = _add_historical_references(service, document.id)
    service.cloud_sync_service.queue.enqueue(document.id, "UPLOAD", "ONEDRIVE")
    used_before = service.get_storage_usage().used_bytes
    stored_path = Path(document.storage_path)
    service.delete_document(document.id)

    assert service.permanently_delete_document(document.id) is True

    assert service.get_document(document.id) is None
    assert not stored_path.exists()
    assert service.get_storage_usage().used_bytes == used_before - document.size
    assert service.database.fetch_one(
        "SELECT id FROM document_requests WHERE id=?", (references["request"],)
    )
    assert service.database.fetch_one(
        "SELECT id FROM document_deliveries WHERE id=?", (references["delivery"],)
    )
    item = service.database.fetch_one(
        "SELECT * FROM document_delivery_items WHERE id=?", (references["item"],)
    )
    assert item["document_id"] is None
    assert item["logical_name"] == "contrato.pdf" and item["sha256"] == "a" * 64
    assert service.database.fetch_one(
        "SELECT id FROM delivery_acknowledgement_receipts WHERE id=?",
        (references["receipt"],),
    )
    assert service.database.fetch_one(
        "SELECT 1 FROM document_request_documents WHERE document_id=?", (document.id,)
    ) is None
    assert service.database.fetch_one(
        "SELECT 1 FROM sync_jobs WHERE document_id=?", (document.id,)
    ) is None
    history = service.database.fetch_all(
        "SELECT action,document_id FROM history WHERE description LIKE ?",
        (f"%{document.name}%",),
    )
    assert history and all(row["document_id"] is None for row in history)
    assert service.database.fetch_all("PRAGMA foreign_key_check") == []


def test_permanent_delete_rolls_file_and_database_back_on_failure(tmp_path: Path, monkeypatch):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    source = tmp_path / "rollback.pdf"
    source.write_bytes(b"rollback-content")
    document = service.import_document(str(source), sync_cloud=False)
    service.delete_document(document.id)
    stored_path = Path(document.storage_path)
    used_before = service.get_storage_usage().used_bytes

    def fail_delete(*_args, **_kwargs):
        raise RuntimeError("falha transacional simulada")

    monkeypatch.setattr(service.document_repository, "hard_delete", fail_delete)
    with pytest.raises(RuntimeError, match="falha transacional"):
        service.permanently_delete_document(document.id)

    assert stored_path.read_bytes() == b"rollback-content"
    assert service.get_document(document.id).status == "TRASHED"
    assert service.get_storage_usage().used_bytes == used_before
    assert service.database.fetch_all("PRAGMA foreign_key_check") == []


def test_empty_trash_handles_linked_and_unlinked_documents(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first_source = tmp_path / "linked.pdf"
    second_source = tmp_path / "ordinary.pdf"
    first_source.write_bytes(b"linked-document")
    second_source.write_bytes(b"ordinary-document")
    linked = service.import_document(str(first_source), sync_cloud=False)
    ordinary = service.import_document(str(second_source), sync_cloud=False)
    references = _add_historical_references(service, linked.id)
    service.delete_document(linked.id)
    service.delete_document(ordinary.id)

    assert service.empty_trash() == 2

    assert service.get_document(linked.id) is None
    assert service.get_document(ordinary.id) is None
    assert service.database.fetch_one(
        "SELECT id FROM document_requests WHERE id=?", (references["request"],)
    )
    assert service.database.fetch_one(
        "SELECT document_id FROM document_delivery_items WHERE id=?",
        (references["item"],),
    )["document_id"] is None
    assert service.database.fetch_all("PRAGMA foreign_key_check") == []


def test_cloud_accounts_and_jobs_are_strictly_isolated_by_organization(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first_id = service.active_organization_id
    second = service.organization_service.create("Empresa B")
    manager = service.cloud_manager
    first = manager.save_authentication_result(
        first_id, "ONEDRIVE", CloudAuthResult(access_token="token-a")
    )
    second_account = manager.save_authentication_result(
        second.id, "GOOGLE_DRIVE", CloudAuthResult(access_token="token-b")
    )
    manager.configure(first_id, "ONEDRIVE", first.id)
    manager.configure(second.id, "GOOGLE_DRIVE", second_account.id)

    with pytest.raises(CloudAccountOwnershipError):
        manager.account(first.id, second.id)
    with pytest.raises(CloudAccountOwnershipError):
        manager.configure(second.id, "ONEDRIVE", first.id)
    assert manager.active_account_for("ONEDRIVE", first_id).access_token == "token-a"
    assert manager.active_account_for("GOOGLE_DRIVE", second.id).access_token == "token-b"

    source = tmp_path / "isolated.pdf"
    source.write_bytes(b"isolated")
    document_a = service.import_document(str(source), sync_cloud=False)
    with pytest.raises(ValueError, match="não pertence"):
        service.cloud_sync_service.enqueue_upload(document_a.id, second.id)

    manager.remove_account(second.id)
    assert manager.active_account_for("ONEDRIVE", first_id).id == first.id
    assert manager.settings(first_id).sync_mode == "ONEDRIVE"
    assert manager.settings(second.id).sync_mode == "LOCAL"
    assert service.database.fetch_all("PRAGMA foreign_key_check") == []


def test_schema_20_shared_cloud_account_is_split_safely_on_migration(tmp_path: Path):
    path = tmp_path / "legacy-v20.db"
    service = DocumentService(db_path=str(path))
    first_id = service.active_organization_id
    second_id = service.organization_service.create("Empresa legada").id
    service.database.close()

    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.executescript(
        """
        DROP TABLE cloud_folder_mappings;
        DROP TABLE cloud_settings;
        DROP TABLE cloud_accounts;
        CREATE TABLE cloud_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL,
            email TEXT, display_name TEXT, access_token TEXT NOT NULL,
            refresh_token TEXT, expires_at TEXT, status TEXT NOT NULL,
            created_at TEXT NOT NULL, token_ref TEXT UNIQUE
        );
        CREATE TABLE cloud_settings (
            organization_id INTEGER PRIMARY KEY, cloud_account_id INTEGER,
            sync_mode TEXT NOT NULL DEFAULT 'LOCAL', remote_root_id TEXT,
            last_sync TEXT, delta_token TEXT, paused INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE cloud_folder_mappings (
            organization_id INTEGER NOT NULL, folder_id INTEGER NOT NULL,
            provider TEXT NOT NULL, remote_id TEXT NOT NULL,
            remote_parent_id TEXT, remote_name TEXT NOT NULL,
            synced_at TEXT NOT NULL, cloud_account_id INTEGER,
            management_mode TEXT NOT NULL DEFAULT 'MANAGED',
            PRIMARY KEY (organization_id,folder_id,provider)
        );
        """
    )
    connection.execute(
        """INSERT INTO cloud_accounts VALUES
           (7,'ONEDRIVE','shared@example.com','Compartilhada','TOKEN_STORE',
            'TOKEN_STORE',NULL,'ACTIVE',?,'cloud:shared-v20')""",
        (_now(),),
    )
    connection.executemany(
        """INSERT INTO cloud_settings(
               organization_id,cloud_account_id,sync_mode,remote_root_id,paused
           ) VALUES (?,7,'ONEDRIVE',?,0)""",
        ((first_id, "root-a"), (second_id, "root-b")),
    )
    connection.execute("PRAGMA user_version=20")
    connection.commit()
    connection.close()

    migrated = Database(str(path))
    assert migrated.fetch_one("PRAGMA user_version")[0] == CURRENT_SCHEMA_VERSION == 21
    rows = migrated.fetch_all(
        "SELECT * FROM cloud_accounts ORDER BY organization_id"
    )
    assert len(rows) == 2
    assert {row["organization_id"] for row in rows} == {first_id, second_id}
    assert sum(row["token_ref"] == "cloud:shared-v20" for row in rows) == 1
    secondary = next(row for row in rows if row["token_ref"] is None)
    assert secondary["status"] == "REAUTH_REQUIRED"
    settings = migrated.fetch_all(
        "SELECT * FROM cloud_settings ORDER BY organization_id"
    )
    assert all(row["cloud_account_id"] is not None for row in settings)
    assert migrated.fetch_all("PRAGMA foreign_key_check") == []
