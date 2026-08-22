from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QApplication

from app.cloud.cloud_models import (
    CloudStorageQuota, CloudStorageQuotaStatus,
)
from app.cloud.cloud_provider import (
    CloudAuthenticationError, CloudError, CloudOfflineError,
    CloudPermissionDeniedError,
)
from app.cloud.providers.google_drive_provider import GoogleDriveProvider
from app.cloud.providers.onedrive_provider import OneDriveProvider
from app.services.cloud_storage_quota_service import CloudStorageQuotaService
from app.views.document_view import DocumentView
from app.workers.cloud_storage_quota_worker import CloudStorageQuotaWorker


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_APP = None


def _app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _transport(payload, calls):
    def send(method, url, headers, data):
        calls.append((method, url))
        return 200, {}, json.dumps(payload).encode()
    return send


def test_onedrive_quota_normal_and_full():
    calls = []
    normal = OneDriveProvider("token", _transport({
        "quota": {"total": 1000, "used": 400, "remaining": 600, "state": "normal"}
    }, calls)).get_storage_quota()
    full = OneDriveProvider("token", _transport({
        "quota": {"total": 1000, "used": 1000, "remaining": 0, "state": "exceeded"}
    }, [])).get_storage_quota()

    assert normal.total_bytes == 1000 and normal.percent == 40
    assert normal.available_bytes == 600
    assert full.available_bytes == 0 and full.percent == 100
    assert calls == [("GET", f"{OneDriveProvider.GRAPH}/me/drive?$select=quota")]


def test_google_drive_quota_normal_full_and_unlimited():
    normal = GoogleDriveProvider("token", _transport({
        "storageQuota": {"limit": "2000", "usage": "500", "usageInDrive": "400"}
    }, [])).get_storage_quota()
    full = GoogleDriveProvider("token", _transport({
        "storageQuota": {"limit": "2000", "usage": "2000"}
    }, [])).get_storage_quota()
    unlimited = GoogleDriveProvider("token", _transport({
        "storageQuota": {"usage": "500"}
    }, [])).get_storage_quota()

    assert (normal.total_bytes, normal.used_bytes, normal.available_bytes) == (2000, 500, 1500)
    assert full.available_bytes == 0 and full.percent == 100
    assert unlimited.total_bytes is None and unlimited.used_bytes == 500
    assert unlimited.percent is None


@pytest.mark.parametrize("provider", [OneDriveProvider, GoogleDriveProvider])
def test_incomplete_quota_response_is_not_reported_as_zero(provider):
    with pytest.raises(CloudError, match="incompleta"):
        provider("token", _transport({}, [])).get_storage_quota()


class _Settings:
    sync_mode = "ONEDRIVE"
    cloud_account_id = 7


class _Manager:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def settings(self, organization_id):
        self.calls.append(("settings", organization_id))
        return _Settings()

    def quota_provider_for(self, organization_id):
        self.calls.append(("provider", organization_id))
        return self.provider


class _QuotaProvider:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def get_storage_quota(self):
        if self.error:
            raise self.error
        return self.result


def _quota():
    return CloudStorageQuota(
        provider="ONEDRIVE", total_bytes=100, used_bytes=25,
        available_bytes=75, fetched_at=datetime.now(timezone.utc),
        status=CloudStorageQuotaStatus.AVAILABLE,
    )


def test_service_uses_requested_organization_and_local_does_not_call_provider():
    manager = _Manager(_QuotaProvider(_quota()))
    service = CloudStorageQuotaService(manager)
    assert service.fetch(42).used_bytes == 25
    assert ("provider", 42) in manager.calls

    manager.calls.clear()
    settings = _Settings(); settings.sync_mode = "LOCAL"; settings.cloud_account_id = None
    manager.settings = lambda organization_id: settings
    assert service.fetch(99) is None
    assert manager.calls == []


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (CloudOfflineError("offline"), CloudStorageQuotaStatus.TEMPORARILY_UNAVAILABLE),
        (CloudAuthenticationError("expired"), CloudStorageQuotaStatus.AUTHENTICATION_REQUIRED),
        (CloudPermissionDeniedError("forbidden"), CloudStorageQuotaStatus.PERMISSION_DENIED),
    ],
)
def test_quota_worker_failure_isolated_and_finished(error, status):
    manager = _Manager(_QuotaProvider(error=error))
    service = CloudStorageQuotaService(manager)
    failures = []
    finished = []
    worker = CloudStorageQuotaWorker(service, 1, "ONEDRIVE")
    worker.failed.connect(failures.append)
    worker.finished.connect(lambda: finished.append(True))
    worker.start(); assert worker.wait(3000)
    _app().processEvents()

    assert failures and failures[0].status == status
    assert finished == [True]


def test_quota_worker_success_and_view_separates_local_from_remote():
    _app()
    service = CloudStorageQuotaService(_Manager(_QuotaProvider(_quota())))
    results = []
    worker = CloudStorageQuotaWorker(service, 3, "ONEDRIVE")
    worker.succeeded.connect(results.append)
    worker.start(); assert worker.wait(3000)
    _app().processEvents()
    assert results[0].percent == 25

    view = DocumentView()
    view.set_cloud_quota(results[0])
    assert "OneDrive" in view.cloud_quota_label.text()
    assert "SmartFile local" not in view.cloud_quota_label.text()
    view.close()
