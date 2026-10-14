from dataclasses import fields, replace

from app.entities.audit_log_entity import AuditLogEntity
from app.repositories.base_repository import BaseRepository


class AuditLogRepository(BaseRepository):
    COLUMNS = tuple(field.name for field in fields(AuditLogEntity) if field.name != "id")

    def create(self, entity: AuditLogEntity) -> AuditLogEntity:
        cursor = self._write(
            f"INSERT INTO audit_log ({','.join(self.COLUMNS)}) VALUES ({','.join('?' for _ in self.COLUMNS)})",
            tuple(getattr(entity, column) for column in self.COLUMNS),
        )
        return replace(entity, id=cursor.lastrowid)

    def find_validation_document_snapshot(self, organization_id, validation_id):
        return self._fetch_one(
            """SELECT document_uuid, document_name, source_type, target_id
               FROM audit_log WHERE organization_id=? AND target_type='document'
               AND document_uuid IS NOT NULL
               AND json_extract(CASE WHEN json_valid(details_json) THEN details_json
                                ELSE '{}' END, '$.validation_id')=?
               ORDER BY id ASC LIMIT 1""",
            (organization_id, validation_id),
        )

    def find_by_organization(self, organization_id: int, limit: int = 100, **filters):
        clauses, parameters = ["organization_id=?"], [organization_id]
        for field in ("actor_username", "document_uuid", "action", "instance_id"):
            if filters.get(field):
                clauses.append(f"{field}=?")
                parameters.append(filters[field])
        if filters.get("document_id") is not None:
            clauses += ["target_type='document'", "target_id=?"]
            parameters.append(filters['document_id'])
        if filters.get("document_name"):
            clauses.append("document_name LIKE ? ESCAPE '\\'")
            name = filters['document_name'].replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            parameters.append(f"%{name}%")
        for field, operator in (("from_date", ">="), ("to_date", "<=")):
            if filters.get(field):
                clauses.append(f"julianday(created_at){operator}julianday(?)")
                parameters.append(filters[field])
        parameters.append(max(1, min(int(limit), 5000)))
        rows = self._fetch_all(
            f"SELECT * FROM audit_log WHERE {' AND '.join(clauses)} ORDER BY created_at DESC,id DESC LIMIT ?",
            parameters,
        )
        return [AuditLogEntity(**dict(row)) for row in rows]
