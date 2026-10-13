from dataclasses import fields
from app.entities.validation_record import ValidationRecord
from app.repositories.base_repository import BaseRepository


class ValidationRepository(BaseRepository):
    COLUMNS = tuple(field.name for field in fields(ValidationRecord) if field.name != "id")

    def create_pending(self, values):
        columns = tuple(values)
        if any(column not in self.COLUMNS for column in columns):
            raise ValueError("Campo de validação inválido.")
        with self.database.transaction() as connection:
            cursor = connection.execute(
                f"INSERT INTO validation_records ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(values.values()),
            )
            return self.get_by_id(cursor.lastrowid, values["organization_id"])

    def get_by_id(self, record_id, organization_id):
        return self._entity(self._fetch_one(
            "SELECT * FROM validation_records WHERE id=? AND organization_id=?",
            (record_id, organization_id)))

    def lookup(self, column, value, organization_id):
        if column not in {"public_token", "human_code", "final_sha256"}:
            raise ValueError("Consulta inválida.")
        return self._entity(self._fetch_one(
            f"SELECT * FROM validation_records WHERE {column}=? AND organization_id=? ORDER BY id DESC LIMIT 1",
            (value, organization_id)))

    def list_by_document(self, document_id, organization_id):
        return [self._entity(row) for row in self._fetch_all(
            "SELECT * FROM validation_records WHERE document_id=? AND organization_id=? ORDER BY id DESC",
            (document_id, organization_id))]

    def activate(self, record, artifact, signed_at=None, receipt_id=None):
        changed = self._write(
            """UPDATE validation_records SET artifact_storage_ref=?,artifact_size=?,final_sha256=?,
               signed_at=?,receipt_id=COALESCE(?,receipt_id),status='ACTIVE'
               WHERE id=? AND organization_id=? AND status='PENDING'""",
            (artifact.storage_ref, artifact.size, artifact.sha256, signed_at, receipt_id,
             record.id, record.organization_id))
        if changed.rowcount != 1:
            raise ValueError("Registro não está pendente; ativação recusada.")
        return self.get_by_id(record.id, record.organization_id)

    def fail(self, record):
        self._write("UPDATE validation_records SET status='FAILED' WHERE id=? AND organization_id=? AND status='PENDING'",
                    (record.id, record.organization_id))

    def revoke(self, record, now, user_id, reason):
        changed = self._write(
            """UPDATE validation_records SET status='REVOKED',revoked_at=?,revoked_by_user_id=?,revocation_reason=?
               WHERE id=? AND organization_id=? AND status='ACTIVE'""",
            (now, user_id, reason, record.id, record.organization_id))
        if changed.rowcount != 1:
            raise ValueError("Somente registro ACTIVE pode ser revogado.")
        return self.get_by_id(record.id, record.organization_id)

    @staticmethod
    def _entity(row):
        return ValidationRecord(**dict(row)) if row else None
