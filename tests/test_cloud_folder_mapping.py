from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import (
    CloudFolderManagementMode, RemoteItemType, RemoteMetadata,
)
from app.cloud.cloud_provider import (
    CloudAuthenticationError, CloudOfflineError, CloudPermissionDeniedError,
    CloudResourceNotFoundError,
)
from app.cloud.cloud_sync_service import CloudSyncService
from app.cloud.providers.onedrive_provider import OneDriveProvider
from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.errors.cloud_folder_mapping_exceptions import (
    CloudFolderMappingConflictError, InvalidRemoteFolderError,
)
from app.services.cloud_folder_mapping_service import CloudFolderMappingService
from app.services.folder_service import FolderService
from app.views.cloud_folder_mapping_dialog import CloudFolderMappingDialog
from app.views.document_view import DocumentView


class FolderProvider:
    def __init__(self):
        self.items: dict[str, RemoteMetadata] = {}
        self.ensure_calls = []
        self.rename_calls = []
        self.move_calls = []
        self.delete_calls = []

    def get_metadata(self, remote_id):
        if remote_id not in self.items:
            raise CloudResourceNotFoundError("Pasta remota ausente")
        return self.items[remote_id]

    def ensure_folder(self, name, parent_id=None):
        self.ensure_calls.append((name, parent_id))
        item = RemoteMetadata(
            f"managed-{len(self.ensure_calls)}", name, parent_id=parent_id,
            item_type=RemoteItemType.FOLDER,
        )
        self.items[item.remote_id] = item
        return item

    def rename(self, remote_id, name):
        self.rename_calls.append((remote_id, name))
        current = self.get_metadata(remote_id)
        updated = RemoteMetadata(
            remote_id, name, parent_id=current.parent_id,
            item_type=current.item_type,
        )
        self.items[remote_id] = updated
        return updated

    def move(self, remote_id, parent_id):
        self.move_calls.append((remote_id, parent_id))
        current = self.get_metadata(remote_id)
        updated = RemoteMetadata(
            remote_id, current.name, parent_id=parent_id,
            item_type=current.item_type,
        )
        self.items[remote_id] = updated
        return updated

    def delete(self, remote_id):
        self.delete_calls.append(remote_id)

    def list_folders(self, parent_id=None):
        return [
            item for item in self.items.values()
            if item.parent_id == parent_id and item.item_type == RemoteItemType.FOLDER
        ]

    def list_changes(self, cursor=None):
        return [], cursor


def _configured(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    organization_id = database.fetch_one("SELECT id FROM organizations LIMIT 1")["id"]
    account_id = database.execute_query(
        """INSERT INTO cloud_accounts(
               organization_id,provider,email,display_name,access_token,refresh_token,
               expires_at,status,created_at,token_ref
           ) VALUES (?,'ONEDRIVE','test@example.com','Test','TOKEN_STORE',
                     'TOKEN_STORE',NULL,'ACTIVE',?,NULL)""",
        (organization_id, datetime.now(timezone.utc).isoformat()),
    ).lastrowid
    database.execute_query(
        """UPDATE cloud_settings SET cloud_account_id=?,sync_mode='ONEDRIVE',
               remote_root_id='org-root',paused=0 WHERE organization_id=?""",
        (account_id, organization_id),
    )
    manager = CloudManager(database)
    folders = FolderService(database)
    local = folders.create(organization_id, "Contratos")
    provider = FolderProvider()
    provider.items["org-root"] = RemoteMetadata(
        "org-root", f"Minha Organização ({organization_id})",
        item_type=RemoteItemType.FOLDER,
    )
    provider.items["remote-contracts"] = RemoteMetadata(
        "remote-contracts", "Contratos Corporativos", parent_id="external-parent",
        item_type=RemoteItemType.FOLDER,
    )
    return database, manager, organization_id, account_id, local, provider


def test_onedrive_lists_root_subfolder_and_all_pages_with_folder_identity():
    calls = []
    next_url = "https://graph.microsoft.com/v1.0/next-page"

    def transport(method, url, _headers, _data):
        calls.append((method, url))
        if url == next_url:
            payload = {"value": [{
                "id": "folder-2", "name": "Financeiro", "folder": {},
                "parentReference": {"id": "root"},
            }]}
        else:
            payload = {
                "value": [
                    {"id": "file-1", "name": "arquivo.pdf", "file": {}},
                    {"id": "folder-1", "name": "Contratos", "folder": {}},
                ],
                "@odata.nextLink": next_url,
            }
        return 200, {}, json.dumps(payload).encode()

    provider = OneDriveProvider("token", transport)
    folders = provider.list_folders()
    assert [item.remote_id for item in folders] == ["folder-1", "folder-2"]
    assert all(item.item_type == RemoteItemType.FOLDER for item in folders)
    assert calls[0][1].startswith(f"{provider.GRAPH}/me/drive/root/children?")
    assert calls[1][1] == next_url

    calls.clear()
    provider.list_folders("folder/id")
    assert "/me/drive/items/folder%2Fid/children?" in calls[0][1]


def test_onedrive_folder_listing_rejects_repeated_page_and_http_errors():
    repeated = "https://graph.microsoft.com/v1.0/repeated"

    def loop_transport(_method, _url, _headers, _data):
        return 200, {}, json.dumps({"value": [], "@odata.nextLink": repeated}).encode()

    with pytest.raises(Exception, match="repetiu"):
        OneDriveProvider("token", loop_transport).list_folders()

    for status, error_type in (
        (401, CloudAuthenticationError),
        (403, CloudPermissionDeniedError),
        (404, CloudResourceNotFoundError),
        (503, CloudOfflineError),
    ):
        provider = OneDriveProvider(
            "token", lambda *_args, status=status: (status, {}, b"{}")
        )
        with pytest.raises(error_type):
            provider.list_folders()


def test_mapping_adopts_remote_identity_without_modifying_or_importing(tmp_path: Path):
    database, manager, organization_id, account_id, local, provider = _configured(tmp_path)
    service = CloudFolderMappingService(database, manager)
    before = database.fetch_one("SELECT COUNT(*) total FROM documents")["total"]

    mapping = service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )

    assert mapping.remote_id == "remote-contracts"
    assert mapping.cloud_account_id == account_id
    assert mapping.management_mode == CloudFolderManagementMode.ADOPTED
    assert mapping.remote_parent_id == "external-parent"
    assert not provider.ensure_calls
    assert not provider.rename_calls
    assert not provider.move_calls
    assert not provider.delete_calls
    assert database.fetch_one("SELECT COUNT(*) total FROM documents")["total"] == before


def test_adopted_mapping_is_reused_without_rename_move_or_duplicate(tmp_path: Path):
    database, manager, organization_id, _account_id, local, provider = _configured(tmp_path)
    mapping_service = CloudFolderMappingService(database, manager)
    mapping_service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    FolderService(database).rename(organization_id, local.id, "Nome local alterado")

    CloudSyncService(database, manager).synchronize_structure(
        organization_id, provider=provider, reconcile_documents=False,
    )

    assert not provider.ensure_calls
    assert not provider.rename_calls
    assert not provider.move_calls
    persisted = mapping_service.current(organization_id, local.id)
    assert persisted.remote_name == "Contratos Corporativos"
    assert persisted.remote_parent_id == "external-parent"


def test_duplicate_remote_mapping_and_non_folder_are_rejected(tmp_path: Path):
    database, manager, organization_id, _account_id, local, provider = _configured(tmp_path)
    service = CloudFolderMappingService(database, manager)
    service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    second = FolderService(database).create(organization_id, "Financeiro")
    with pytest.raises(CloudFolderMappingConflictError, match="já está mapeada"):
        service.map_existing_onedrive_folder(
            organization_id, second.id, "remote-contracts", provider=provider,
        )
    provider.items["a-file"] = RemoteMetadata(
        "a-file", "arquivo.pdf", item_type=RemoteItemType.FILE,
    )
    with pytest.raises(InvalidRemoteFolderError):
        service.map_existing_onedrive_folder(
            organization_id, second.id, "a-file", provider=provider,
        )


def test_existing_local_mapping_can_be_consciously_changed_or_report_missing(tmp_path: Path):
    database, manager, organization_id, _account_id, local, provider = _configured(tmp_path)
    service = CloudFolderMappingService(database, manager)
    service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    provider.items["remote-finance"] = RemoteMetadata(
        "remote-finance", "Financeiro", parent_id="other-parent",
        item_type=RemoteItemType.FOLDER,
    )
    changed = service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-finance", provider=provider,
    )
    assert changed.remote_id == "remote-finance"
    assert "remote-contracts" in provider.items
    assert not provider.rename_calls and not provider.move_calls and not provider.delete_calls
    with pytest.raises(CloudResourceNotFoundError):
        service.map_existing_onedrive_folder(
            organization_id, local.id, "missing", provider=provider,
        )


def test_unmap_and_local_folder_delete_never_delete_adopted_remote(tmp_path: Path):
    database, manager, organization_id, _account_id, local, provider = _configured(tmp_path)
    service = CloudFolderMappingService(database, manager)
    service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    assert service.remove_mapping(organization_id, local.id)
    assert not provider.delete_calls
    assert service.current(organization_id, local.id) is None

    service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    FolderService(database).delete(organization_id, local.id)
    CloudSyncService(database, manager).synchronize_structure(
        organization_id, provider=provider, reconcile_documents=True,
    )
    assert not provider.delete_calls
    assert service.current(organization_id, local.id) is None


def test_account_change_invalidates_mappings_and_remote_ids(tmp_path: Path):
    database, manager, organization_id, _account_id, local, provider = _configured(tmp_path)
    service = CloudFolderMappingService(database, manager)
    service.map_existing_onedrive_folder(
        organization_id, local.id, "remote-contracts", provider=provider,
    )
    new_account_id = database.execute_query(
        """INSERT INTO cloud_accounts(
               organization_id,provider,email,display_name,access_token,refresh_token,
               expires_at,status,created_at,token_ref
           ) VALUES (?,'ONEDRIVE','other@example.com','Other','TOKEN_STORE',
                     'TOKEN_STORE',NULL,'ACTIVE',?,NULL)""",
        (organization_id, datetime.now(timezone.utc).isoformat()),
    ).lastrowid
    manager.configure(organization_id, "ONEDRIVE", new_account_id)
    assert service.current(organization_id, local.id) is None
    assert service.mappings.find_all(organization_id, "ONEDRIVE") == []


def test_schema_19_persists_adoption_identity(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    assert database.fetch_one("PRAGMA user_version")[0] == CURRENT_SCHEMA_VERSION == 21
    columns = {
        row["name"] for row in database.fetch_all("PRAGMA table_info(cloud_folder_mappings)")
    }
    assert {"cloud_account_id", "management_mode"} <= columns


def test_schema_18_is_migrated_incrementally_without_losing_mapping(tmp_path: Path):
    path = tmp_path / "legacy.db"
    database = Database(str(path))
    organization_id = database.fetch_one("SELECT id FROM organizations LIMIT 1")["id"]
    folder = FolderService(database).create(organization_id, "Legado")
    connection = database.connect()
    connection.executescript(
        """
        DROP INDEX IF EXISTS idx_cloud_folder_account_remote;
        DROP INDEX IF EXISTS idx_cloud_folder_account;
        ALTER TABLE cloud_folder_mappings RENAME TO cloud_folder_mappings_v19;
        CREATE TABLE cloud_folder_mappings (
            organization_id INTEGER NOT NULL,
            folder_id INTEGER NOT NULL,
            provider TEXT NOT NULL,
            remote_id TEXT NOT NULL,
            remote_parent_id TEXT,
            remote_name TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            PRIMARY KEY (organization_id, folder_id, provider)
        );
        """
    )
    connection.execute(
        "INSERT INTO cloud_folder_mappings VALUES (?,?,?,?,?,?,?)",
        (organization_id, folder.id, "ONEDRIVE", "legacy-id", None, "Legado", "now"),
    )
    connection.execute("DROP TABLE cloud_folder_mappings_v19")
    connection.execute("PRAGMA user_version=18")
    database.close()

    migrated = Database(str(path))
    row = migrated.fetch_one("SELECT * FROM cloud_folder_mappings")
    assert migrated.fetch_one("PRAGMA user_version")[0] == 21
    assert row["remote_id"] == "legacy-id"
    assert row["management_mode"] == "MANAGED"
    assert row["cloud_account_id"] is None


def test_dialog_browses_in_worker_and_can_close_during_request():
    app = QApplication.instance() or QApplication([])
    entered = threading.Event()

    class SlowProvider:
        def list_folders(self, _parent=None):
            entered.set()
            time.sleep(0.08)
            return [RemoteMetadata(
                "remote", "Contratos", item_type=RemoteItemType.FOLDER,
            )]

    dialog = CloudFolderMappingDialog(
        SlowProvider(), "Minha Organização / Clientes", "OneDrive — test@example.com",
    )
    worker = dialog._worker
    assert worker is not None and worker.isRunning()
    assert entered.wait(1)
    dialog.reject()
    assert worker.isInterruptionRequested()
    assert worker.wait(2000)
    app.processEvents()
    assert worker not in CloudFolderMappingDialog._live_workers
    dialog.close()


def test_mapping_action_requires_logical_folder_and_explicit_availability():
    app = QApplication.instance() or QApplication([])
    view = DocumentView()
    view.set_cloud_folder_mapping(None, True)
    view._update_more_menu()
    assert not view.map_cloud_folder_action.isEnabled()
    root = view.folder_tree.topLevelItem(0)
    assert root is None

    from types import SimpleNamespace
    view.set_folders("Minha Organização", [
        SimpleNamespace(id=10, parent_id=None, name="Contratos"),
    ])
    folder = view.folder_tree.topLevelItem(0).child(0)
    view.folder_tree.setCurrentItem(folder)
    app.processEvents()
    view.set_cloud_folder_mapping(None, True)
    assert view.map_cloud_folder_action.isEnabled()
    view._select_scope("trash")
    assert not view.map_cloud_folder_action.isEnabled()
    view.close()
