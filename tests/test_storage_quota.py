from datetime import timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.database.database import Database
from app.errors.storage_exceptions import InsufficientLocalDiskSpaceError, StorageQuotaError, StorageQuotaExceededError
from app.errors.storage_exceptions import CloudStorageLimitError
from app.cloud.cloud_models import CloudOperation
from app.services.document_service import DocumentService
from app.services.storage_quota_service import GB, StorageQuotaService


def test_default_plans_are_configured_in_gb(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)

    plans = {plan.code: plan.quota_bytes for plan in quota.plans.find_all()}

    assert plans == {
        "PERSONAL_10GB": 10 * GB,
        "STUDENT_20GB": 20 * GB,
        "BUSINESS_60GB": 60 * GB,
    }


@pytest.mark.parametrize(
    ("template", "plan", "quota_bytes"),
    [
        ("PERSONAL", "PERSONAL_10GB", 10 * GB),
        ("STUDENT", "STUDENT_20GB", 20 * GB),
        ("BUSINESS", "BUSINESS_60GB", 60 * GB),
        ("EMPTY", "PERSONAL_10GB", 10 * GB),
    ],
)
def test_template_and_storage_plan_are_separate(tmp_path: Path, template, plan, quota_bytes):
    service = DocumentService(db_path=str(tmp_path / f"{template}.db"))
    organization = service.organization_service.create(template, template_code=template)
    persisted = service.organization_service.repository.find_by_id(organization.id)
    summary = service.storage_quota_service.get_usage_summary(organization.id)

    assert persisted.template_code == template
    assert persisted.storage_plan_code == plan
    assert summary.quota_bytes == quota_bytes


def test_reserve_commit_release_and_limit(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]
    database.execute_query(
        "UPDATE organization_storage SET quota_bytes=10, used_bytes=0, reserved_bytes=0 WHERE organization_id=?",
        (organization_id,),
    )

    first = quota.reserve(organization_id, 6, "first")
    assert quota.get_reserved(organization_id) == 6
    with pytest.raises(StorageQuotaExceededError):
        quota.reserve(organization_id, 5, "too-large")
    quota.commit_reservation(first)
    assert quota.get_used(organization_id) == 6
    assert quota.get_reserved(organization_id) == 0

    second = quota.reserve(organization_id, 4, "equal-limit")
    quota.release_reservation(second)
    assert quota.get_available(organization_id) == 4


def test_expired_reservation_is_released(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]

    quota.reserve(organization_id, 7, "expired", expires_in=timedelta(seconds=-1))

    assert quota.cleanup_expired() == 1
    assert quota.get_reserved(organization_id) == 0
    assert quota.reservations.find_by_operation("expired").status == "EXPIRED"


def test_concurrent_reservations_cannot_exceed_quota(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]
    database.execute_query(
        "UPDATE organization_storage SET quota_bytes=10, used_bytes=0, reserved_bytes=0 WHERE organization_id=?",
        (organization_id,),
    )

    def attempt(operation):
        try:
            quota.reserve(organization_id, 6, operation)
            return "reserved"
        except StorageQuotaExceededError:
            return "blocked"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, ("parallel-a", "parallel-b")))

    assert sorted(results) == ["blocked", "reserved"]
    assert quota.get_reserved(organization_id) == 6


def test_insufficient_local_disk_has_distinct_error(tmp_path: Path, monkeypatch):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]
    usage = type("Usage", (), {"total": 100, "used": 99, "free": 1})()
    monkeypatch.setattr("app.services.storage_quota_service.shutil.disk_usage", lambda _path: usage)

    with pytest.raises(InsufficientLocalDiskSpaceError, match="disco local"):
        quota.reserve(organization_id, 2, "no-disk")


def test_import_scanner_updates_usage_metadata_and_cloud_queue(tmp_path: Path):
    source = tmp_path / "scan.pdf"
    source.write_bytes(b"digitalizacao")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))

    document = service.import_document(
        str(source), title="Contrato digitalizado", category="Contratos",
        description="Duas páginas", tags="cliente, contrato", document_date="2026-07-13",
        notes="Mesa de vidro", source_type="SCANNER",
    )

    assert document.source_type == "SCANNER"
    assert document.name == "Contrato digitalizado.pdf"
    assert document.tags == "cliente, contrato"
    assert document.document_date == "2026-07-13"
    assert service.get_storage_usage().used_bytes == source.stat().st_size
    history = service.history_service.list_history(document.id)
    assert any(item.action == "SCAN" for item in history)


def test_trash_keeps_usage_copy_consumes_and_permanent_delete_releases(tmp_path: Path):
    source = tmp_path / "document.pdf"
    source.write_bytes(b"123456789")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    original = service.import_document(str(source))
    copied = service.copy_document(original.id)

    assert service.get_storage_usage().used_bytes == 18
    service.delete_document(original.id)
    assert service.get_storage_usage().used_bytes == 18
    assert service.permanently_delete_document(original.id)
    assert service.get_storage_usage().used_bytes == 9
    assert Path(copied.storage_path).is_file()


def test_recalculate_usage_corrects_inconsistency(tmp_path: Path):
    source = tmp_path / "document.pdf"
    source.write_bytes(b"correct-size")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    service.import_document(str(source))
    service.database.execute_query(
        "UPDATE organization_storage SET used_bytes=0 WHERE organization_id=?",
        (service.active_organization_id,),
    )

    assert service.recalculate_storage_usage() == len(b"correct-size")
    assert service.get_storage_usage().used_bytes == len(b"correct-size")


class _DownloadProvider:
    def __init__(self, content: bytes):
        self.content = content

    def download(self, _remote_id, destination):
        destination.write_bytes(self.content)
        return destination


def test_cloud_download_growth_respects_and_updates_quota(tmp_path: Path):
    source = tmp_path / "cloud.pdf"
    source.write_bytes(b"old")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    imported = service.import_document(str(source))
    entity = service.document_repository.find_by_id(imported.id)
    entity.remote_id = "remote-1"

    service.cloud_sync_service._download(_DownloadProvider(b"new-content"), entity)

    refreshed = service.document_repository.find_by_id(imported.id)
    assert Path(refreshed.storage_path).read_bytes() == b"new-content"
    assert refreshed.size == len(b"new-content")
    assert service.get_storage_usage().used_bytes == len(b"new-content")


def test_cloud_download_over_quota_preserves_local_document(tmp_path: Path):
    source = tmp_path / "cloud.pdf"
    source.write_bytes(b"old")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    imported = service.import_document(str(source))
    entity = service.document_repository.find_by_id(imported.id)
    entity.remote_id = "remote-1"
    service.database.execute_query(
        "UPDATE organization_storage SET quota_bytes=used_bytes WHERE organization_id=?",
        (service.active_organization_id,),
    )

    with pytest.raises(StorageQuotaExceededError):
        service.cloud_sync_service._download(_DownloadProvider(b"larger-remote-content"), entity)

    assert Path(imported.storage_path).read_bytes() == b"old"
    assert service.get_storage_usage().used_bytes == len(b"old")


class _FullProvider:
    def upload(self, _request):
        raise CloudStorageLimitError("sem espaço")


def test_remote_quota_failure_keeps_local_document_and_safe_message(tmp_path: Path):
    source = tmp_path / "local.pdf"
    source.write_bytes(b"local-preserved")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    document = service.import_document(str(source), sync_cloud=False)
    service.cloud_sync_service.queue.enqueue(document.id, CloudOperation.UPLOAD, "ONEDRIVE")
    service.cloud_manager.provider_for = lambda _organization_id: _FullProvider()

    service.cloud_sync_service.process_next()

    refreshed = service.get_document(document.id)
    job = service.cloud_sync_service.queue.get(1)
    assert refreshed.cloud_status == "SYNC_ERROR"
    assert Path(refreshed.storage_path).read_bytes() == b"local-preserved"
    assert "armazenamento da nuvem está cheio" in job.last_error


@pytest.mark.parametrize(
    ("used", "level"), [(79, "NORMAL"), (80, "ATENÇÃO"), (90, "CRÍTICO"), (100, "BLOQUEADO")]
)
def test_usage_alert_thresholds(tmp_path: Path, used: int, level: str):
    database = Database(str(tmp_path / f"level-{used}.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]
    database.execute_query(
        "UPDATE organization_storage SET quota_bytes=100, used_bytes=? WHERE organization_id=?",
        (used, organization_id),
    )

    assert quota.get_usage_summary(organization_id).level == level


def test_plan_cannot_be_reduced_below_current_usage(tmp_path: Path):
    database = Database(str(tmp_path / "smartfile.db"))
    quota = StorageQuotaService(database)
    organization_id = database.fetch_one("SELECT id FROM organizations WHERE is_default=1")["id"]
    database.execute_query(
        "UPDATE organization_storage SET used_bytes=? WHERE organization_id=?",
        (11*GB, organization_id),
    )

    with pytest.raises(StorageQuotaError, match="menor que o uso"):
        quota.assign_plan(organization_id, "PERSONAL_10GB", "PERSONAL")
