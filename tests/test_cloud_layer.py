from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.cloud.cloud_job_queue import CloudJobQueue
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_models import (
    CloudAuthResult, CloudOperation, CloudSyncState, CloudUploadRequest, RemoteMetadata,
)
from app.cloud.cloud_provider import CloudOfflineError, CloudProvider
from app.cloud.cloud_sync_service import CloudSyncService
from app.cloud.providers.google_drive_provider import GoogleDriveProvider
from app.cloud.providers.onedrive_provider import OneDriveProvider
from app.database.database import Database
from app.services.document_service import DocumentService
from app.workers.cloud_download_worker import CloudDownloadWorker
from app.workers.cloud_sync_worker import CloudSyncWorker
from app.workers.cloud_upload_worker import CloudUploadWorker


class FakeProvider(CloudProvider):
    def __init__(self, offline=False):
        super().__init__("fake-token")
        self.offline = offline
        self.uploaded = []

    def authenticate(self, credentials): return CloudAuthResult(access_token="token")
    def refresh_token(self, refresh_token, credentials): return CloudAuthResult(access_token="refreshed")

    def upload(self, request):
        if self.offline:
            raise CloudOfflineError("offline")
        self.uploaded.append(request.local_path)
        return RemoteMetadata("remote-1", request.remote_name, request.local_path.stat().st_size, "v1")

    def download(self, remote_id, destination): destination.write_bytes(b"remote"); return destination
    def delete(self, remote_id): return None
    def rename(self, remote_id, new_name): return RemoteMetadata(remote_id, new_name)
    def move(self, remote_id, parent_id): return RemoteMetadata(remote_id, "file", parent_id=parent_id)
    def list_changes(self, cursor=None): return [], "cursor-2"
    def get_metadata(self, remote_id): return RemoteMetadata(remote_id, "file")
    def disconnect(self): self.access_token = ""


def _account(manager: CloudManager, provider="ONEDRIVE", expired=False):
    expires = datetime.now(timezone.utc) - timedelta(minutes=1) if expired else datetime.now(timezone.utc) + timedelta(hours=1)
    return manager._save_account(provider, CloudAuthResult(
        access_token="secret-access-token", refresh_token="secret-refresh-token",
        expires_at=expires, email="teste@example.com", display_name="Conta Teste",
    ))


def test_tokens_are_encrypted_and_active_account_is_per_organization(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    manager = CloudManager(database)
    account = _account(manager)
    organization = database.fetch_one("SELECT id FROM organizations WHERE is_default = 1")
    manager.configure(organization["id"], "ONEDRIVE", account.id)

    raw = database.fetch_one("SELECT access_token, refresh_token FROM cloud_accounts WHERE id = ?", (account.id,))
    assert "secret-access-token" not in raw["access_token"]
    assert "secret-refresh-token" not in raw["refresh_token"]
    assert manager.account(account.id).access_token == "secret-access-token"
    assert manager.settings(organization["id"]).sync_mode == "ONEDRIVE"
    assert (database.data_dir / ".cloud_tokens.key").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    ("provider_class", "token_fragment", "profile_fragment"),
    [
        (OneDriveProvider, "oauth2/v2.0/token", "graph.microsoft.com/v1.0/me"),
        (GoogleDriveProvider, "oauth2.googleapis.com/token", "openidconnect.googleapis.com"),
    ],
)
def test_oauth_login_contract_for_both_providers(provider_class, token_fragment, profile_fragment):
    calls = []

    def transport(method, url, headers, data):
        calls.append((method, url, headers, data))
        if token_fragment in url:
            return 200, {}, json.dumps({"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}).encode()
        if profile_fragment in url:
            profile = {"displayName": "Pessoa", "mail": "pessoa@example.com"} if "graph" in url else {"name": "Pessoa", "email": "pessoa@example.com"}
            return 200, {}, json.dumps(profile).encode()
        raise AssertionError(url)

    provider = provider_class(transport=transport)
    begin = provider.authenticate({"action": "begin", "client_id": "client", "redirect_uri": "http://localhost"})
    result = provider.authenticate({
        "action": "complete", "client_id": "client", "redirect_uri": "http://localhost",
        "code": "authorization-code", "code_verifier": begin.code_verifier,
    })

    assert begin.authorization_url and "code_challenge=" in begin.authorization_url
    assert result.access_token == "access" and result.email == "pessoa@example.com"
    assert all("authorization-code" not in str(headers) for _method, _url, headers, _data in calls)


@pytest.mark.parametrize("provider_class", [OneDriveProvider, GoogleDriveProvider])
def test_provider_upload_download_and_metadata(provider_class, tmp_path: Path):
    source = tmp_path / "documento.pdf"; source.write_bytes(b"pdf-data")

    def transport(method, url, headers, data):
        if method in {"PUT", "POST", "PATCH"}:
            payload = {"id": "remote-7", "name": "documento.pdf", "size": 8, "eTag": "v1", "version": "2"}
            return 200, {}, json.dumps(payload).encode()
        if "alt=media" in url or url.endswith("/content"):
            return 200, {}, b"downloaded"
        return 200, {}, json.dumps({"id": "remote-7", "name": "documento.pdf"}).encode()

    provider = provider_class("access", transport)
    metadata = provider.upload(CloudUploadRequest(source, source.name))
    destination = provider.download(metadata.remote_id, tmp_path / "download.pdf")

    assert metadata.remote_id == "remote-7"
    assert destination.read_bytes() == b"downloaded"


def test_offline_import_stays_local_queue_retries_and_reconnects(tmp_path: Path):
    source = tmp_path / "documento.pdf"; source.write_bytes(b"conteudo local")
    documents = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    manager = documents.cloud_manager
    account = _account(manager)
    manager.configure(documents.active_organization_id, "ONEDRIVE", account.id)

    document = documents.import_document(str(source))
    stored = Path(document.storage_path)
    assert stored.is_file() and document.cloud_status == CloudSyncState.PENDING_UPLOAD

    fake = FakeProvider(offline=True)
    manager.provider_for = lambda _organization_id: fake
    documents.cloud_sync_service.process_next()
    retry_document = documents.get_document(document.id)
    assert retry_document.cloud_status == CloudSyncState.PENDING_UPLOAD
    assert CloudJobQueue(documents.database).next_pending().status == "RETRY"
    assert stored.read_bytes() == b"conteudo local"

    fake.offline = False
    documents.cloud_sync_service.process_next()
    synced = documents.get_document(document.id)
    assert synced.cloud_status == CloudSyncState.SYNCED
    assert synced.remote_id == "remote-1"
    assert stored.is_file()


def test_queue_persists_and_settings_change_with_organization(tmp_path: Path):
    source = tmp_path / "file.pdf"; source.write_bytes(b"x")
    documents = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first = documents.import_document(str(source))
    company = documents.organization_service.create("Empresa")
    account = _account(documents.cloud_manager, "GOOGLE_DRIVE")
    documents.cloud_manager.configure(company.id, "GOOGLE_DRIVE", account.id)
    documents.set_active_organization(company.id)
    second = documents.import_document(str(source))

    reopened = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    assert reopened.active_organization_id == company.id
    assert reopened.cloud_manager.settings(company.id).sync_mode == "GOOGLE_DRIVE"
    assert reopened.cloud_sync_service.queue.pending_count() == 1
    reopened.set_active_organization(first.organization_id)
    assert reopened.cloud_manager.settings(first.organization_id).sync_mode == "LOCAL"
    assert reopened.get_document(second.id) is None


def test_expired_token_is_refreshed_without_exposing_secret(tmp_path: Path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db"))

    def transport(method, url, headers, data):
        assert "refresh_token=secret-refresh-token" in data.decode()
        return 200, {}, json.dumps({"access_token": "new-access", "expires_in": 3600}).encode()

    manager = CloudManager(database, transport)
    account = _account(manager, expired=True)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default = 1")["id"]
    manager.configure(organization_id, "ONEDRIVE", account.id)
    monkeypatch.setenv("SMARTFILE_ONEDRIVE_CLIENT_ID", "client")

    provider = manager.provider_for(organization_id)

    assert provider.access_token == "new-access"
    raw = database.fetch_one("SELECT access_token FROM cloud_accounts WHERE id = ?", (account.id,))["access_token"]
    assert "new-access" not in raw


def test_cloud_workers_keep_native_finished_signal():
    assert "finished" not in CloudUploadWorker.__dict__
    assert "finished" not in CloudDownloadWorker.__dict__
    assert "finished" not in CloudSyncWorker.__dict__
