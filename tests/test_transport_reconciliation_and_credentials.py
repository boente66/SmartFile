from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.database.migrations import _upgrade_transport_targets
from app.errors.transport_exceptions import (
    CredentialInUseError,
    CredentialVaultUnavailableError,
    TransportReconciliationError,
)
from app.models.registration_request import RegistrationRequest
from app.models.transport_credential import TransportCredential
from app.security.credential_provider import CredentialProvider
from app.services.auth_service import AuthService
from app.services.document_service import DocumentService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_transport_service import OrganizationTransportService


class MemoryCredentialProvider(CredentialProvider):
    def __init__(self, *, unavailable: bool = False):
        self.secrets: dict[str, str] = {}
        self.unavailable = unavailable

    def _available(self) -> None:
        if self.unavailable:
            raise CredentialVaultUnavailableError("Cofre indisponível para teste.")

    def store(self, reference: str, secret: str) -> None:
        self._available()
        self.secrets[reference] = secret

    def get(self, reference: str) -> str | None:
        self._available()
        return self.secrets.get(reference)

    def delete(self, reference: str) -> None:
        self._available()
        self.secrets.pop(reference, None)

    def exists(self, reference: str) -> bool:
        self._available()
        return reference in self.secrets


def _stack(tmp_path: Path, provider: CredentialProvider | None = None):
    database = Database(str(tmp_path / "smartfile.db"))
    context = SessionContext()
    AuthService(database, context).register_first_user(RegistrationRequest(
        display_name="Administrador", username="admin",
        email="admin@example.com", password="senha-segura",
        password_confirmation="senha-segura", template_code="BUSINESS",
        organization_name="Empresa",
    ))
    policy = OrganizationFeatureService(database, context)
    enabled = set(policy.for_organization(context.active_organization).codes)
    policy.update_enabled_features(
        context.active_organization, enabled | {"server_transport"},
    )
    documents = DocumentService(database=database)
    transport = OrganizationTransportService(
        database, context, credential_provider=provider,
    )
    return database, context, documents, transport


def _source(tmp_path: Path, name: str, content: bytes) -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    return path


def test_jobs_keep_immutable_target_and_new_documents_use_new_target(tmp_path: Path):
    database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas_a = tmp_path / "nas-a"; nas_a.mkdir()
    nas_b = tmp_path / "nas-b"; nas_b.mkdir()
    first_setting = transport.configure(
        organization_id, "NAS", str(nas_a), enabled=True,
    )
    first = documents.import_document(
        str(_source(tmp_path, "primeiro.pdf", b"primeiro")), sync_cloud=False,
    )
    first_job = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, first.id, "UPLOAD",
    )

    second_setting = transport.configure(
        organization_id, "NAS", str(nas_b), enabled=True,
    )
    second = documents.import_document(
        str(_source(tmp_path, "segundo.pdf", b"segundo")), sync_cloud=False,
    )
    second_job = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, second.id, "UPLOAD",
    )

    assert first_setting.current_target_id != second_setting.current_target_id
    assert first_job.transport_target_id == first_setting.current_target_id
    assert second_job.transport_target_id == second_setting.current_target_id
    assert transport.targets.find_by_id(first_setting.current_target_id).status == "RETIRED"
    completed_a = documents.corporate_transport_service.process_next(organization_id)
    completed_b = documents.corporate_transport_service.process_next(organization_id)
    assert Path(completed_a.remote_path).is_relative_to(nas_a)
    assert Path(completed_b.remote_path).is_relative_to(nas_b)
    assert database.fetch_one(
        "SELECT endpoint FROM organization_transport_targets WHERE id=?",
        (first_job.transport_target_id,),
    )["endpoint"] == str(nas_a)
    target_events = database.fetch_all(
        "SELECT action, target_id FROM audit_log "
        "WHERE organization_id=? AND target_type='transport_target'",
        (organization_id,),
    )
    assert ("TRANSPORT_TARGET_RETIRED", first_setting.current_target_id) in {
        (row["action"], row["target_id"]) for row in target_events
    }
    assert ("TRANSPORT_TARGET_ACTIVATED", second_setting.current_target_id) in {
        (row["action"], row["target_id"]) for row in target_events
    }


def test_delete_after_target_change_uses_original_target(tmp_path: Path):
    _database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas_a = tmp_path / "nas-a"; nas_a.mkdir()
    nas_b = tmp_path / "nas-b"; nas_b.mkdir()
    setting_a = transport.configure(organization_id, "NAS", str(nas_a), enabled=True)
    document = documents.import_document(
        str(_source(tmp_path, "delete.pdf", b"delete")), sync_cloud=False,
    )
    upload = documents.corporate_transport_service.process_next(organization_id)
    remote_a = Path(upload.remote_path)
    transport.configure(organization_id, "NAS", str(nas_b), enabled=True)

    documents.delete_document(document.id)
    documents.permanently_delete_document(document.id)
    delete_job = documents.corporate_transport_service.queue.next_pending(organization_id)
    assert delete_job.transport_target_id == setting_a.current_target_id
    completed = documents.corporate_transport_service.process_next(organization_id)
    assert completed.status == "COMPLETED"
    assert not remote_a.exists()
    assert not any(nas_b.rglob("*.pdf"))


def test_retry_after_target_change_still_uses_original_target(tmp_path: Path):
    _database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas_a = tmp_path / "offline-a"
    nas_b = tmp_path / "nas-b"; nas_b.mkdir()
    setting_a = transport.configure(organization_id, "NAS", str(nas_a), enabled=True)
    document = documents.import_document(
        str(_source(tmp_path, "retry.pdf", b"retry")), sync_cloud=False,
    )
    retry = documents.corporate_transport_service.process_next(organization_id)
    assert retry.status == "RETRY"
    transport.configure(organization_id, "NAS", str(nas_b), enabled=True)
    nas_a.mkdir()

    completed = documents.corporate_transport_service.process_next(organization_id)
    assert completed.transport_target_id == setting_a.current_target_id
    assert Path(completed.remote_path).is_relative_to(nas_a)
    assert not any(nas_b.rglob("*.pdf"))
    assert completed.document_id == document.id


def test_switch_to_local_pauses_old_jobs_and_does_not_mass_delete(tmp_path: Path):
    database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas_a = tmp_path / "nas-a"; nas_a.mkdir()
    setting_a = transport.configure(organization_id, "NAS", str(nas_a), enabled=True)
    first = documents.import_document(
        str(_source(tmp_path, "pending.pdf", b"pending")), sync_cloud=False,
    )
    old_job = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, first.id, "UPLOAD",
    )
    transport.configure(organization_id, "LOCAL", None, enabled=False)
    documents.import_document(
        str(_source(tmp_path, "local.pdf", b"local")), sync_cloud=False,
    )

    assert not documents.corporate_transport_service.automatic_processing_enabled(
        organization_id
    )
    assert old_job.transport_target_id == setting_a.current_target_id
    assert database.fetch_one(
        "SELECT COUNT(*) AS total FROM transport_jobs WHERE operation='DELETE'"
    )["total"] == 0
    assert database.fetch_one(
        "SELECT COUNT(*) AS total FROM transport_jobs"
    )["total"] == 1


def test_unresolved_job_cannot_be_processed_or_marked_running(tmp_path: Path):
    database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    transport.configure(organization_id, "NAS", str(nas), enabled=True)
    document = documents.import_document(
        str(_source(tmp_path, "legacy.pdf", b"legacy")), sync_cloud=False,
    )
    job = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, document.id, "UPLOAD",
    )
    database.execute_query(
        "UPDATE transport_jobs SET transport_target_id=NULL, "
        "reconciliation_status='NEEDS_RECONCILIATION' WHERE id=?", (job.id,),
    )

    assert documents.corporate_transport_service.process_next(organization_id) is None
    assert not documents.corporate_transport_service.queue.repository.mark_running(job.id)
    with pytest.raises(TransportReconciliationError):
        documents.corporate_transport_service.process_job(job.id)


def test_reconciliation_can_cancel_or_recreate_without_mutating_original(
    tmp_path: Path,
):
    database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    setting = transport.configure(organization_id, "NAS", str(nas), enabled=True)
    first = documents.import_document(
        str(_source(tmp_path, "recriar.pdf", b"recriar")), sync_cloud=False,
    )
    original = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, first.id, "UPLOAD",
    )
    database.execute_query(
        "UPDATE transport_jobs SET transport_target_id=NULL, "
        "reconciliation_status='NEEDS_RECONCILIATION' WHERE id=?", (original.id,),
    )
    replacement = transport.recreate_upload(organization_id, original.id)

    assert documents.corporate_transport_service.queue.get(original.id).status == "CANCELLED"
    assert replacement.id != original.id
    assert replacement.transport_target_id == setting.current_target_id
    assert replacement.reconciliation_status == "RESOLVED"

    second = documents.import_document(
        str(_source(tmp_path, "cancelar.pdf", b"cancelar")), sync_cloud=False,
    )
    uncertain = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, second.id, "UPLOAD",
    )
    database.execute_query(
        "UPDATE transport_jobs SET transport_target_id=NULL, "
        "reconciliation_status='NEEDS_RECONCILIATION' WHERE id=?", (uncertain.id,),
    )
    assert transport.cancel_reconciliation(organization_id, uncertain.id)
    assert documents.corporate_transport_service.queue.get(uncertain.id).status == "CANCELLED"


def test_migration_resolves_only_provable_remote_paths(tmp_path: Path):
    database, context, documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    setting = transport.configure(organization_id, "NAS", str(nas), enabled=True)
    uploaded_document = documents.import_document(
        str(_source(tmp_path, "enviado.pdf", b"enviado")), sync_cloud=False,
    )
    uploaded = documents.corporate_transport_service.process_next(organization_id)
    pending_document = documents.import_document(
        str(_source(tmp_path, "pendente.pdf", b"pendente")), sync_cloud=False,
    )
    pending = documents.corporate_transport_service.queue.repository.find_active(
        organization_id, pending_document.id, "UPLOAD",
    )
    database.execute_query(
        "UPDATE transport_jobs SET transport_target_id=NULL, "
        "reconciliation_status='NEEDS_RECONCILIATION' WHERE id IN (?, ?)",
        (uploaded.id, pending.id),
    )

    _upgrade_transport_targets(database.connect())
    migrated_upload = documents.corporate_transport_service.queue.get(uploaded.id)
    migrated_pending = documents.corporate_transport_service.queue.get(pending.id)
    assert migrated_upload.document_id == uploaded_document.id
    assert migrated_upload.transport_target_id == setting.current_target_id
    assert migrated_upload.reconciliation_status == "RESOLVED"
    assert migrated_pending.transport_target_id is None
    assert migrated_pending.reconciliation_status == "NEEDS_RECONCILIATION"


def test_transport_target_entity_is_immutable(tmp_path: Path):
    _database, context, _documents, transport = _stack(tmp_path)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    setting = transport.configure(organization_id, "NAS", str(nas), enabled=True)
    target = transport.targets.find_by_id(setting.current_target_id)
    with pytest.raises(FrozenInstanceError):
        target.endpoint = str(tmp_path / "outro")
    assert not hasattr(transport.targets, "update")


def test_vault_store_get_exists_and_delete(tmp_path: Path):
    provider = MemoryCredentialProvider()
    _database, context, _documents, transport = _stack(tmp_path, provider)
    organization_id = context.active_organization.id
    reference = transport.credentials.store(
        organization_id, TransportCredential("usuario", "segredo"),
    )
    assert transport.credentials.exists(organization_id, reference)
    credential = transport.credentials.get(organization_id, reference)
    assert (credential.username, credential.password) == ("usuario", "segredo")
    transport.credentials.delete(organization_id, reference)
    assert not provider.exists(reference)


def test_credential_rotation_preserves_old_secret_and_sqlite_has_no_secret(
    tmp_path: Path, caplog,
):
    provider = MemoryCredentialProvider()
    database, context, documents, transport = _stack(tmp_path, provider)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    first = transport.configure(
        organization_id, "NAS", str(nas), enabled=True,
        credential_username="usuario-a", credential_password="SEGREDO-A-UNICO",
    )
    document = documents.import_document(
        str(_source(tmp_path, "credencial.pdf", b"credencial")), sync_cloud=False,
    )
    second = transport.configure(
        organization_id, "NAS", str(nas), enabled=True,
        credential_username="usuario-b", credential_password="SEGREDO-B-UNICO",
    )
    target_a = transport.targets.find_by_id(first.current_target_id)
    target_b = transport.targets.find_by_id(second.current_target_id)

    assert target_a.credential_ref != target_b.credential_ref
    assert target_a.credential_ref in provider.secrets
    assert target_b.credential_ref in provider.secrets
    restarted_service = OrganizationTransportService(
        database, context, credential_provider=provider,
    )
    restarted_credential = restarted_service.credentials.get(
        organization_id, target_b.credential_ref,
    )
    assert restarted_credential.username == "usuario-b"
    assert restarted_credential.password == "SEGREDO-B-UNICO"
    assert documents.corporate_transport_service.queue.repository.find_active(
        organization_id, document.id, "UPLOAD",
    ).transport_target_id == target_a.id
    database.connect().execute("PRAGMA wal_checkpoint(FULL)")
    raw = database.db_path.read_bytes()
    assert b"SEGREDO-A-UNICO" not in raw and b"SEGREDO-B-UNICO" not in raw
    audit = " ".join(
        str(row["description"] or "") for row in database.fetch_all(
            "SELECT description FROM audit_log"
        )
    )
    assert "SEGREDO" not in audit
    assert "SEGREDO-A-UNICO" not in caplog.text
    assert "SEGREDO-B-UNICO" not in caplog.text
    with pytest.raises(CredentialInUseError):
        transport.credentials.delete(organization_id, target_a.credential_ref)


def test_switch_to_local_detaches_but_preserves_required_historical_credential(
    tmp_path: Path,
):
    provider = MemoryCredentialProvider()
    _database, context, documents, transport = _stack(tmp_path, provider)
    organization_id = context.active_organization.id
    nas = tmp_path / "nas"; nas.mkdir()
    remote = transport.configure(
        organization_id, "NAS", str(nas), enabled=True,
        credential_username="usuario", credential_password="SEGREDO-HISTORICO",
    )
    documents.import_document(
        str(_source(tmp_path, "historico.pdf", b"historico")), sync_cloud=False,
    )
    old_target = transport.targets.find_by_id(remote.current_target_id)

    local = transport.configure(organization_id, "LOCAL", None, enabled=False)

    assert local.current_target_id is None and local.credential_ref is None
    assert transport.targets.find_by_id(old_target.id).status == "RETIRED"
    assert old_target.credential_ref in provider.secrets


def test_vault_failure_and_database_failure_preserve_configuration(
    tmp_path: Path, monkeypatch,
):
    unavailable = MemoryCredentialProvider(unavailable=True)
    _db, context, _documents, transport = _stack(tmp_path / "unavailable", unavailable)
    organization_id = context.active_organization.id
    with pytest.raises(CredentialVaultUnavailableError):
        transport.configure(
            organization_id, "NAS", str(tmp_path / "nas"), enabled=True,
            credential_username="user", credential_password="NAO-PERSISTIR",
        )
    assert transport.get(organization_id).mode == "LOCAL"

    provider = MemoryCredentialProvider()
    _db2, context2, _documents2, transport2 = _stack(tmp_path / "database", provider)
    organization_id2 = context2.active_organization.id
    monkeypatch.setattr(
        transport2.repository, "save",
        lambda _entity: (_ for _ in ()).throw(RuntimeError("db indisponível")),
    )
    with pytest.raises(RuntimeError):
        transport2.configure(
            organization_id2, "NAS", str(tmp_path / "nas-2"), enabled=True,
            credential_username="user", credential_password="COMPENSAR-SEGREDO",
        )
    assert provider.secrets == {}


def test_credential_management_requires_permission(tmp_path: Path):
    provider = MemoryCredentialProvider()
    _database, context, _documents, transport = _stack(tmp_path, provider)
    organization_id = context.active_organization.id
    context.permissions = {"organization.view"}
    with pytest.raises(Exception, match="Permissão insuficiente"):
        transport.configure(
            organization_id, "NAS", str(tmp_path / "nas"), enabled=True,
            credential_username="user", credential_password="secret",
        )
    assert provider.secrets == {}
