"""Local validation: locator, byte integrity, administrative status and signature are independent."""
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.entities.validation_record import ArtifactType, SignatureType
from app.models.document_validation_result import DocumentValidationResult
from app.repositories.validation_repository import ValidationRepository
from app.services.audit_service import AuditService
from app.services.canonical_artifact_service import CanonicalArtifactService
from app.services.validation_locator_service import ValidationLocatorService


class DocumentValidationService:
    CODE_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

    def __init__(self, database, context=None):
        self.database = database
        self.context = context
        self.repository = ValidationRepository(database=database)
        self.artifacts = CanonicalArtifactService(database.paths)
        self.audit = AuditService(database)

    def active_organization_id(self):
        if self.context is not None:
            return getattr(self.context.active_organization, "id", None)
        row = self.database.fetch_one("SELECT value FROM app_settings WHERE key='active_organization_id'")
        if row and row[0]:
            return int(row[0])
        return self.database.fetch_one("SELECT id FROM organizations WHERE is_default=1")[0]

    def _require(self, organization_id, permission):
        if self.context is not None:
            if organization_id != getattr(self.context.active_organization, "id", None):
                raise PermissionError("Ative a organização do registro antes desta operação.")
            self.context.require_permission(permission)
        row = self.database.fetch_one("SELECT status FROM organizations WHERE id=?", (organization_id,))
        if row is None or row[0] != "ACTIVE":
            raise PermissionError("Organização indisponível.")

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()

    def _user_id(self):
        return getattr(getattr(self.context, "current_user", None), "id", None)

    def _audit(self, action, record):
        self.audit.record(action, organization_id=record.organization_id,
                          user_id=self._user_id(), target_type="validation_record", target_id=record.id)

    def base_url(self, organization_id):
        self._require(organization_id, "validation.view")
        row = self.database.fetch_one("SELECT value FROM app_settings WHERE key=?",
                                      (f"validation_base_url:{organization_id}",))
        return row[0] if row and row[0] else None

    def configure(self, organization_id, base_url):
        self._require(organization_id, "validation.configure")
        value = ValidationLocatorService.validate_base_url(base_url.strip() if base_url else None)
        with self.database.transaction() as connection:
            connection.execute("INSERT INTO app_settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                               (f"validation_base_url:{organization_id}", value))
            self.audit.record("VALIDATION_CONFIGURED", organization_id=organization_id, user_id=self._user_id())

    def create_pending(self, organization_id, *, logical_name, artifact_type, signature_type,
                       document_id=None, delivery_id=None, receipt_id=None, protocol=None):
        # Internal receipt flow uses the existing acknowledge permission; callers
        # cannot select arbitrary permissions.
        required = "delivery.acknowledge" if artifact_type == ArtifactType.DELIVERY_RECEIPT else "validation.create"
        self._require(organization_id, required)
        artifact_type = ArtifactType(artifact_type).value
        signature_type = SignatureType(signature_type).value
        combinations = {ArtifactType.SIGNED_DOCUMENT: SignatureType.A1_PADES,
                        ArtifactType.VISUAL_SIGNED_DOCUMENT: SignatureType.VISUAL_HANDWRITTEN,
                        ArtifactType.UNSIGNED_REGISTERED_DOCUMENT: SignatureType.NONE,
                        ArtifactType.DELIVERY_RECEIPT: SignatureType.VISUAL_HANDWRITTEN}
        if combinations[artifact_type] != signature_type:
            raise ValueError("Tipo de artefato e assinatura incompatíveis.")
        for table, identifier in (("documents", document_id), ("document_deliveries", delivery_id),
                                  ("delivery_acknowledgement_receipts", receipt_id)):
            if identifier is not None:
                row = self.database.fetch_one(f"SELECT organization_id FROM {table} WHERE id=?", (identifier,))
                if row is None or row[0] != organization_id:
                    raise PermissionError("Vínculo histórico não pertence à organização.")
        base = self.base_url(organization_id)
        for _ in range(8):
            try:
                with self.database.transaction():
                    record = self.repository.create_pending(dict(
                        organization_id=organization_id, public_token="SFV1-" + secrets.token_urlsafe(32),
                        human_code="SFV" + "".join(secrets.choice(self.CODE_ALPHABET) for _ in range(16)),
                        artifact_type=artifact_type, signature_type=signature_type,
                        logical_name_snapshot=Path(logical_name).name[:200], protocol_snapshot=protocol,
                        document_id=document_id, delivery_id=delivery_id, receipt_id=receipt_id,
                        created_at=self._now(), created_by_user_id=self._user_id(),
                        base_url_snapshot=base, locator_mode="WEB" if base else "LOCAL"))
                    self._audit("VALIDATION_CREATED", record)
                    return record
            except sqlite3.IntegrityError as exc:
                if "public_token" not in str(exc) and "human_code" not in str(exc):
                    raise
        raise ValueError("Não foi possível gerar identificadores únicos.")

    def activate(self, record, source, *, signed_at=None, receipt_id=None):
        self._require(record.organization_id, "validation.view")
        current = self.repository.get_by_id(record.id, record.organization_id)
        if current is None:
            raise PermissionError("Registro não encontrado na organização ativa.")
        required = "delivery.acknowledge" if current.artifact_type == ArtifactType.DELIVERY_RECEIPT else "validation.create"
        self._require(current.organization_id, required)
        if self.context is not None and current.created_by_user_id != self._user_id():
            raise PermissionError("Somente o criador pode finalizar este registro pendente.")
        if current.status != "PENDING":
            raise ValueError("Sobrescrita de registro finalizado recusada.")
        if receipt_id is not None:
            row = self.database.fetch_one("SELECT organization_id FROM delivery_acknowledgement_receipts WHERE id=?", (receipt_id,))
            if not row or row[0] != record.organization_id:
                raise PermissionError("Comprovante de outra organização.")
        # A canonical artifact must be an actual readable final PDF.
        import fitz
        with fitz.open(source) as pdf:
            if pdf.page_count < 1:
                raise ValueError("PDF canônico sem páginas.")
        artifact = self.artifacts.preserve(record.organization_id, current.public_token, source)
        with self.database.transaction():
            active = self.repository.activate(current, artifact, signed_at, receipt_id)
            self._audit("VALIDATION_ACTIVATED", active)
        return active

    def fail(self, record):
        self._require(record.organization_id, "validation.view")
        current = self.repository.get_by_id(record.id, record.organization_id)
        if current is None:
            raise PermissionError("Registro não encontrado na organização ativa.")
        required = "delivery.acknowledge" if current.artifact_type == ArtifactType.DELIVERY_RECEIPT else "validation.create"
        self._require(current.organization_id, required)
        if self.context is not None and current.created_by_user_id != self._user_id():
            raise PermissionError("Somente o criador pode cancelar este registro pendente.")
        self._fail_pending(current)

    def _fail_pending(self, record):
        # Compensation is scoped to the captured record, even if the UI changed org.
        with self.database.transaction():
            self.repository.fail(record)
            self._audit("VALIDATION_FAILED", record)

    def finalize(self, producer, *, logical_name, artifact_type, signature_type, document_id=None, source_path=None):
        organization_id = self.active_organization_id()
        if document_id is None and source_path is not None:
            from app.repositories.document_repository import DocumentRepository
            document = DocumentRepository(database=self.database).find_by_scoped_path(Path(source_path).resolve(), organization_id)
            document_id = document.id if document else None
        record = self.create_pending(organization_id, logical_name=logical_name,
                                     artifact_type=artifact_type, signature_type=signature_type,
                                     document_id=document_id)
        try:
            result = producer(ValidationLocatorService.build_payload(record), record.human_code)
            self.activate(record, result.output_path, signed_at=self._now())
            return result
        except Exception:
            self._fail_pending(record)
            raise

    def validate(self, organization_id, locator=None, file_path=None, *, cancelled=lambda: False):
        self._require(organization_id, "validation.view")
        record = None
        supplied_hash = None
        if locator:
            kind, value = ValidationLocatorService.parse(locator)
            record = self.repository.lookup("public_token" if kind == "TOKEN" else "human_code", value, organization_id)
        if file_path:
            supplied_hash, _ = self.artifacts.hash_file(file_path, cancelled)
            if not locator:
                record = self.repository.lookup("final_sha256", supplied_hash, organization_id)
        if record is None:
            return DocumentValidationResult("RECORD_NOT_FOUND", message="Registro não encontrado nesta instalação/fonte de validação.")
        if cancelled():
            raise InterruptedError("Verificação cancelada.")
        state = "FOUND" if record.status in {"ACTIVE", "REVOKED"} else record.status
        if record.status not in {"ACTIVE", "REVOKED"}:
            self._audit("VALIDATION_CHECKED", record)
            return DocumentValidationResult(state, record=record, message="Registro ainda não finalizado ou com falha.")
        try:
            path = self.artifacts.checked_path(record)
            artifact_state = "AVAILABLE"
        except FileNotFoundError:
            path = None
            artifact_state = "ARTIFACT_MISSING"
        except (ValueError, OSError):
            path = None
            artifact_state = "ARTIFACT_CORRUPTED"
        file_state = "NOT_PROVIDED" if supplied_hash is None else (
            "HASH_MATCH" if supplied_hash == record.final_sha256 else "HASH_MISMATCH")
        signatures = ()
        signature_status = trust_status = "NOT_APPLICABLE"
        if record.signature_type == SignatureType.A1_PADES:
            signature_status = trust_status = "INDETERMINATE"
            if path:
                from app.services.pdf_signature_service import PDFSignatureService
                try:
                    signatures = tuple(PDFSignatureService().validate(path))
                    if signatures:
                        if all(s.integrity_ok and s.state in {"VALID", "UNTRUSTED"} for s in signatures):
                            signature_status = "VALID"
                        elif any(s.state in {"INVALID", "MODIFIED", "REVOKED", "EXPIRED"} for s in signatures):
                            signature_status = "INVALID"
                        trust_status = "TRUSTED" if all(s.trusted for s in signatures) else (
                            "UNTRUSTED" if any(s.state == "UNTRUSTED" for s in signatures) else "INDETERMINATE")
                    else:
                        signature_status = "INVALID"
                except Exception:
                    pass
        self._require(organization_id, "validation.view")
        with self.database.transaction():
            self._audit("VALIDATION_CHECKED", record)
            if file_state == "HASH_MISMATCH":
                self._audit("VALIDATION_HASH_MISMATCH", record)
            if artifact_state == "ARTIFACT_CORRUPTED":
                self._audit("VALIDATION_ARTIFACT_CORRUPTED", record)
        return DocumentValidationResult(state, artifact_state, file_state, signature_status,
                                        trust_status, record, signatures)

    def get(self, organization_id, record_id, permission="validation.view"):
        self._require(organization_id, permission)
        record = self.repository.get_by_id(record_id, organization_id)
        if record is None:
            raise PermissionError("Registro não encontrado na organização ativa.")
        return record

    def open_original(self, organization_id, record_id):
        record = self.get(organization_id, record_id)
        if record.status not in {"ACTIVE", "REVOKED"}:
            raise ValueError("Registro sem original finalizado.")
        path = self.artifacts.checked_path(record)
        self._audit("VALIDATION_OPENED", record)
        return path

    def export_original(self, organization_id, record_id, destination):
        record = self.get(organization_id, record_id, "validation.export")
        if record.status not in {"ACTIVE", "REVOKED"}:
            raise ValueError("Registro sem original finalizado.")
        result = self.artifacts.export(record, destination)
        self._audit("VALIDATION_EXPORTED", record)
        return result

    def revoke(self, organization_id, record_id, reason):
        record = self.get(organization_id, record_id, "validation.revoke")
        reason = reason.strip()
        if not reason or len(reason) > 500:
            raise ValueError("Informe o motivo da revogação (até 500 caracteres).")
        with self.database.transaction():
            revoked = self.repository.revoke(record, self._now(), self._user_id(), reason)
            self._audit("VALIDATION_REVOKED", revoked)
        return revoked

    def recover_pending(self, organization_id, hours=24):
        self._require(organization_id, "validation.configure")
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=max(24, hours))).isoformat()
        with self.database.transaction():
            rows = self.database.fetch_all("SELECT id FROM validation_records WHERE organization_id=? AND status='PENDING' AND created_at<?", (organization_id, cutoff))
            for row in rows:
                self._fail_pending(self.repository.get_by_id(row[0], organization_id))
        return len(rows)
