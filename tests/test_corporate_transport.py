from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtTest import QSignalSpy

from app.cloud.cloud_models import CloudAuthResult
from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.entities.organization_feature_setting_entity import OrganizationFeatureSettingEntity
from app.entities.organization_transport_entity import OrganizationTransportEntity
from app.errors.transport_exceptions import (
    TransportCancelledError,
    TransportConfigurationError,
    TransportIntegrityError,
)
from app.repositories.organization_feature_setting_repository import (
    OrganizationFeatureSettingRepository,
)
from app.repositories.organization_transport_repository import OrganizationTransportRepository
from app.services.corporate_transport_service import CorporateTransportService
from app.services.document_service import DocumentService
from app.services.organization_service import OrganizationService
from app.transport.nas_transport_adapter import NASTransportAdapter
from app.transport.transport_models import TransportUploadRequest
from app.workers.transport_worker import TransportWorker


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _configure_nas(
    service: DocumentService, endpoint: Path, organization_id: int | None = None,
    *, feature: bool = True, enabled: bool = True, mode: str = "NAS",
) -> int:
    organization_id = organization_id or service.active_organization_id
    organization = service.organization_service.repository.find_by_id(organization_id)
    organization.profile_code = "BUSINESS"
    service.organization_service.repository.update(organization)
    if feature:
        OrganizationFeatureSettingRepository(database=service.database).save(
            OrganizationFeatureSettingEntity(
                organization_id=organization_id, feature_code="server_transport",
                enabled=True, updated_at=_now(),
            )
        )
    OrganizationTransportRepository(database=service.database).save(
        OrganizationTransportEntity(
            organization_id=organization_id, mode=mode,
            endpoint=str(endpoint) if mode != "LOCAL" else None,
            enabled=enabled, updated_at=_now(),
        )
    )
    return organization_id


def test_nas_adapter_connection_upload_checksum_exists_and_delete(tmp_path: Path):
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    source = tmp_path / "contrato.pdf"
    source.write_bytes(b"contrato empresarial" * 1000)
    progress = []
    adapter = NASTransportAdapter(str(endpoint), "empresa-7")

    connection = adapter.test_connection()
    uploaded = adapter.upload(TransportUploadRequest(
        source, "42_Contrato.pdf", _sha256(source),
        lambda copied, total: progress.append((copied, total)),
    ))

    assert connection.success
    assert uploaded.success and uploaded.checksum == _sha256(source)
    assert Path(uploaded.remote_path).read_bytes() == source.read_bytes()
    assert adapter.exists(uploaded.remote_path)
    assert progress[-1] == (source.stat().st_size, source.stat().st_size)
    assert adapter.delete(uploaded.remote_path).success
    assert not Path(uploaded.remote_path).exists()


def test_nas_adapter_reports_offline_and_rejects_path_traversal(tmp_path: Path):
    endpoint = tmp_path / "offline"
    adapter = NASTransportAdapter(str(endpoint), "empresa-1")
    assert not adapter.test_connection().success

    endpoint.mkdir()
    root = endpoint / "SmartFile" / "empresa-1" / "Documents"
    root.mkdir(parents=True)
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"outside")
    with pytest.raises(TransportConfigurationError):
        adapter.delete(str(outside))


def test_nas_adapter_cleans_temporary_on_checksum_failure_and_cancellation(
    tmp_path: Path,
):
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    source = tmp_path / "arquivo.bin"
    source.write_bytes(b"x" * (NASTransportAdapter.CHUNK_SIZE * 2))
    adapter = NASTransportAdapter(str(endpoint), "empresa-2")

    with pytest.raises(TransportIntegrityError):
        adapter.upload(TransportUploadRequest(source, "1_arquivo.bin", "0" * 64))

    cancel = {"requested": False}
    with pytest.raises(TransportCancelledError):
        adapter.upload(TransportUploadRequest(
            source, "2_arquivo.bin", _sha256(source),
            progress_callback=lambda _copied, _total: cancel.update(requested=True),
            cancellation_requested=lambda: cancel["requested"],
        ))
    root = endpoint / "SmartFile" / "empresa-2" / "Documents"
    assert not list(root.glob("*.part"))
    assert not (root / "1_arquivo.bin").exists()
    assert not (root / "2_arquivo.bin").exists()


def test_import_enqueues_nas_and_processes_with_audit(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "Contrato Fornecedor.pdf"
    source.write_bytes(b"conteudo do contrato")

    document = service.import_document(str(source), sync_cloud=False)
    job = service.corporate_transport_service.queue.next_pending(organization_id)
    completed = service.corporate_transport_service.process_next(organization_id)

    assert job and job.document_id == document.id and job.operation == "UPLOAD"
    assert completed.status == "COMPLETED"
    assert Path(completed.remote_path).name.startswith(f"{document.id}_Contrato")
    assert _sha256(Path(completed.remote_path)) == document.checksum
    assert Path(document.storage_path).is_file()
    actions = {
        row["action"] for row in service.database.fetch_all(
            "SELECT action FROM audit_log WHERE organization_id=?",
            (organization_id,),
        )
    }
    assert {"TRANSPORT_JOB_CREATED", "TRANSPORT_UPLOAD_COMPLETED"} <= actions


def test_checksum_failure_keeps_job_out_of_completed(tmp_path: Path, monkeypatch):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "corrompido.pdf"
    source.write_bytes(b"checksum")
    service.import_document(str(source), sync_cloud=False)
    monkeypatch.setattr(
        NASTransportAdapter, "_checksum", staticmethod(lambda _path: "invalid"),
    )
    job = service.corporate_transport_service.process_next(organization_id)
    assert job.status == "RETRY"
    assert "SHA-256" in job.last_error


def test_nas_offline_retry_then_recovery_preserves_local_document(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas-offline"
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "contrato.pdf"
    source.write_bytes(b"sempre local")
    document = service.import_document(str(source), sync_cloud=False)
    local_path = Path(document.storage_path)

    retry = service.corporate_transport_service.process_next(organization_id)
    assert retry.status == "RETRY" and retry.attempts == 1 and retry.last_error
    assert local_path.read_bytes() == b"sempre local"

    endpoint.mkdir()
    completed = service.corporate_transport_service.process_next(organization_id)
    assert completed.status == "COMPLETED" and completed.attempts == 2
    assert Path(completed.remote_path).read_bytes() == local_path.read_bytes()
    assert local_path.is_file()


def test_retry_is_limited_and_failed_job_can_be_reactivated(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "offline"
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "arquivo.pdf"
    source.write_bytes(b"retry")
    service.import_document(str(source), sync_cloud=False)

    job = None
    for _ in range(service.corporate_transport_service.MAX_ATTEMPTS):
        job = service.corporate_transport_service.process_next(organization_id)
    assert job.status == "FAILED"
    assert service.corporate_transport_service.process_next(organization_id) is None
    assert service.corporate_transport_service.retry_failed(organization_id) == 1
    assert service.corporate_transport_service.queue.next_pending(organization_id)


@pytest.mark.parametrize(
    ("feature", "enabled", "mode"),
    [(False, True, "NAS"), (True, False, "NAS"), (True, True, "LOCAL")],
)
def test_disabled_feature_setting_or_local_mode_does_not_enqueue(
    tmp_path: Path, feature: bool, enabled: bool, mode: str,
):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    _configure_nas(
        service, endpoint, feature=feature, enabled=enabled, mode=mode,
    )
    source = tmp_path / "local.pdf"
    source.write_bytes(b"local")
    document = service.import_document(str(source), sync_cloud=False)
    assert Path(document.storage_path).is_file()
    assert service.database.fetch_one("SELECT id FROM transport_jobs") is None


def test_copy_creates_independent_transport_job(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "original.pdf"
    source.write_bytes(b"original")
    original = service.import_document(str(source), sync_cloud=False)
    copied = service.copy_document(original.id)
    jobs = service.database.fetch_all(
        "SELECT document_id FROM transport_jobs WHERE organization_id=? ORDER BY id",
        (organization_id,),
    )
    assert [row["document_id"] for row in jobs] == [original.id, copied.id]


def test_soft_delete_keeps_nas_and_permanent_delete_enqueues_delete(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "excluir.pdf"
    source.write_bytes(b"delete me")
    document = service.import_document(str(source), sync_cloud=False)
    uploaded = service.corporate_transport_service.process_next(organization_id)
    remote = Path(uploaded.remote_path)

    assert service.delete_document(document.id)
    assert remote.is_file()
    assert service.database.fetch_one(
        "SELECT id FROM transport_jobs WHERE operation='DELETE'"
    ) is None

    assert service.permanently_delete_document(document.id)
    delete_job = service.corporate_transport_service.queue.next_pending(organization_id)
    assert delete_job.operation == "DELETE" and delete_job.document_id == document.id
    assert service.get_document(document.id) is None
    completed = service.corporate_transport_service.process_next(organization_id)
    assert completed.status == "COMPLETED" and not remote.exists()


def test_organizations_are_isolated_between_nas_roots(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first_id = _configure_nas(service, tmp_path / "nas-a")
    (tmp_path / "nas-a").mkdir()
    second = OrganizationService(service.database).create(
        "Empresa B", profile_code="BUSINESS",
    )
    (tmp_path / "nas-b").mkdir()
    second_id = _configure_nas(service, tmp_path / "nas-b", second.id)
    first_source = tmp_path / "a.pdf"
    second_source = tmp_path / "b.pdf"
    first_source.write_bytes(b"organization-a")
    second_source.write_bytes(b"organization-b")

    first = service.import_document(
        str(first_source), organization_id=first_id, sync_cloud=False,
    )
    second_document = service.import_document(
        str(second_source), organization_id=second_id, sync_cloud=False,
    )
    first_job = service.corporate_transport_service.process_next(first_id)
    second_job = service.corporate_transport_service.process_next(second_id)

    assert Path(first_job.remote_path).is_relative_to(tmp_path / "nas-a")
    assert Path(second_job.remote_path).is_relative_to(tmp_path / "nas-b")
    assert Path(first_job.remote_path).read_bytes() == Path(first.storage_path).read_bytes()
    assert Path(second_job.remote_path).read_bytes() == Path(second_document.storage_path).read_bytes()


def test_cloud_and_nas_create_independent_jobs(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    account = service.cloud_manager._save_account("ONEDRIVE", CloudAuthResult(
        access_token="test-access", refresh_token="test-refresh",
        email="test@example.com",
    ))
    service.cloud_manager.configure(organization_id, "ONEDRIVE", account.id)
    source = tmp_path / "duplo.pdf"
    source.write_bytes(b"cloud and nas")
    document = service.import_document(str(source))

    assert service.database.fetch_one(
        "SELECT id FROM sync_jobs WHERE document_id=?", (document.id,),
    )
    assert service.database.fetch_one(
        "SELECT id FROM transport_jobs WHERE document_id=?", (document.id,),
    )
    assert service.get_document(document.id).cloud_status == "PENDING_UPLOAD"


def test_https_and_lan_do_not_pretend_to_have_physical_connector(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    organization_id = _configure_nas(service, tmp_path, mode="HTTPS")
    result = service.corporate_transport_service.test_connection(
        organization_id, mode="HTTPS", endpoint="https://ged.example.com",
    )
    assert not result.success
    assert "não implementado" in result.message


def test_schema_15_migrates_to_16_without_losing_existing_data(tmp_path: Path):
    source_path = tmp_path / "source.db"
    service = DocumentService(db_path=str(source_path))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    document_source = tmp_path / "preservado.pdf"
    document_source.write_bytes(b"preservado")
    document = service.import_document(str(document_source), sync_cloud=False)
    service.database.close()

    legacy_path = tmp_path / "schema15.db"
    shutil.copy2(source_path, legacy_path)
    legacy = Database(str(legacy_path))
    legacy.execute_query("DROP TABLE transport_jobs")
    legacy.execute_query("PRAGMA user_version=15")
    legacy.close()

    migrated = Database(str(legacy_path))
    assert migrated.connect().execute("PRAGMA user_version").fetchone()[0] == 16
    assert CURRENT_SCHEMA_VERSION == 16
    assert migrated.fetch_one("SELECT id FROM documents WHERE id=?", (document.id,))
    assert migrated.fetch_one("SELECT id FROM organizations WHERE id=?", (organization_id,))
    assert migrated.fetch_one(
        "SELECT organization_id FROM organization_feature_settings WHERE organization_id=?",
        (organization_id,),
    )
    assert migrated.fetch_one(
        "SELECT organization_id FROM organization_transport_settings WHERE organization_id=?",
        (organization_id,),
    )
    assert migrated.fetch_one(
        "SELECT organization_id FROM cloud_settings WHERE organization_id=?",
        (organization_id,),
    )
    assert migrated.fetch_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='transport_jobs'"
    )


def test_transport_worker_runs_task_outside_caller_and_emits_result():
    application = QCoreApplication.instance() or QCoreApplication([])
    worker = TransportWorker(
        lambda progress, _cancelled: (
            progress(50, "Transferindo"), {"completed": 1}
        )[1]
    )
    progress_spy = QSignalSpy(worker.progress)
    success_spy = QSignalSpy(worker.succeeded)
    worker.start()
    assert success_spy.wait(3000)
    assert worker.wait(3000)
    application.processEvents()
    assert progress_spy and progress_spy[0] == [50, "Transferindo"]
    assert success_spy[0][0] == {"completed": 1}


def test_running_job_is_recovered_after_application_restart(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))
    endpoint = tmp_path / "nas"
    endpoint.mkdir()
    organization_id = _configure_nas(service, endpoint)
    source = tmp_path / "restart.pdf"
    source.write_bytes(b"restart recovery")
    document = service.import_document(str(source), sync_cloud=False)
    repository = service.corporate_transport_service.queue.repository
    job = repository.find_active(organization_id, document.id, "UPLOAD")
    assert job is not None
    assert repository.mark_running(job.id)
    service.database.close()

    restarted_database = Database(str(db_path))
    recovered_service = CorporateTransportService(restarted_database)
    recovered = recovered_service.queue.get(job.id)

    assert recovered.status == "RETRY"
    assert recovered.attempts == 1
    assert "reinicialização" in (recovered.last_error or "")
