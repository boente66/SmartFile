from __future__ import annotations

from app.entities.document_request_entity import DocumentRequestEntity
from app.repositories.base_repository import BaseRepository


class DocumentRequestRepository(BaseRepository):
    def create(self, entity: DocumentRequestEntity) -> DocumentRequestEntity:
        cursor = self._write(
            """
            INSERT INTO document_requests (
                request_uuid, organization_id, title, description, requested_by_user_id,
                assigned_to_user_id, status, due_at, created_at, updated_at,
                started_at, attended_at, delivered_at, completed_at, cancelled_at,
                origin_instance_id, target_instance_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity.request_uuid, entity.organization_id, entity.title, entity.description,
                entity.requested_by_user_id, entity.assigned_to_user_id,
                entity.status, entity.due_at, entity.created_at,
                entity.updated_at, entity.started_at, entity.attended_at,
                entity.delivered_at, entity.completed_at, entity.cancelled_at,
                entity.origin_instance_id, entity.target_instance_id,
            ),
        )
        entity.id = cursor.lastrowid
        return entity

    def find_by_organization(self, organization_id: int) -> list[DocumentRequestEntity]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                """
                SELECT * FROM document_requests WHERE organization_id=?
                ORDER BY CASE status WHEN 'OPEN' THEN 0 WHEN 'IN_PROGRESS' THEN 1
                         WHEN 'ATTENDED' THEN 2 WHEN 'DELIVERING' THEN 3 ELSE 4 END,
                         COALESCE(due_at, '9999-12-31'), id DESC
                """,
                (organization_id,),
            )
        ]

    def find_by_id(self, request_id: int, organization_id: int | None = None) -> DocumentRequestEntity | None:
        if organization_id is None:
            row = self._fetch_one("SELECT * FROM document_requests WHERE id=?", (request_id,))
        else:
            row = self._fetch_one(
                "SELECT * FROM document_requests WHERE id=? AND organization_id=?",
                (request_id, organization_id),
            )
        return self._entity(row) if row else None

    def find_by_uuid(self, request_uuid: str) -> DocumentRequestEntity | None:
        row = self._fetch_one("SELECT * FROM document_requests WHERE request_uuid=?", (request_uuid,))
        return self._entity(row) if row else None

    def update_route(
        self, request_id: int, organization_id: int,
        origin_instance_id: str, target_instance_id: str,
    ) -> bool:
        return self._write(
            """UPDATE document_requests
            SET origin_instance_id=?, target_instance_id=?
            WHERE id=? AND organization_id=?""",
            (origin_instance_id, target_instance_id, request_id, organization_id),
        ).rowcount > 0

    def update_status(self, request_id: int, organization_id: int, status: str, updated_at: str, timestamp_column: str | None = None) -> bool:
        allowed = {"started_at", "attended_at", "delivered_at", "completed_at", "cancelled_at"}
        timestamp_sql = f", {timestamp_column}=?" if timestamp_column in allowed else ""
        params = [status, updated_at]
        if timestamp_sql:
            params.append(updated_at)
        params.extend((request_id, organization_id))
        return self._write(
            f"UPDATE document_requests SET status=?, updated_at=?{timestamp_sql} WHERE id=? AND organization_id=?",
            tuple(params),
        ).rowcount > 0

    def link_document(self, request_id: int, document_id: int, user_id: int | None, created_at: str) -> None:
        self._write(
            "INSERT OR IGNORE INTO document_request_documents (request_id, document_id, linked_by_user_id, created_at) VALUES (?,?,?,?)",
            (request_id, document_id, user_id, created_at),
        )

    def linked_document_ids(self, request_id: int) -> list[int]:
        return [row["document_id"] for row in self._fetch_all(
            "SELECT document_id FROM document_request_documents WHERE request_id=? ORDER BY created_at", (request_id,)
        )]

    def pending_remote(self, organization_id: int) -> list[DocumentRequestEntity]:
        return [self._entity(row) for row in self._fetch_all(
            """SELECT request.* FROM document_requests request
            WHERE request.organization_id=?
              AND request.origin_instance_id IS NOT NULL
              AND request.target_instance_id IS NOT NULL
              AND request.status='OPEN'
              AND NOT EXISTS (
                  SELECT 1 FROM delivery_history history
                  WHERE history.request_id=request.id
                    AND history.event_type='REQUEST_DISPATCHED'
              )
            ORDER BY request.id LIMIT 20""",
            (organization_id,),
        )]

    @staticmethod
    def _entity(row) -> DocumentRequestEntity:
        return DocumentRequestEntity(
            id=row["id"], organization_id=row["organization_id"], title=row["title"],
            request_uuid=row["request_uuid"],
            description=row["description"], requested_by_user_id=row["requested_by_user_id"],
            assigned_to_user_id=row["assigned_to_user_id"], status=row["status"],
            due_at=row["due_at"], created_at=row["created_at"], updated_at=row["updated_at"],
            started_at=row["started_at"], attended_at=row["attended_at"],
            delivered_at=row["delivered_at"], completed_at=row["completed_at"],
            cancelled_at=row["cancelled_at"],
            origin_instance_id=row["origin_instance_id"], target_instance_id=row["target_instance_id"],
        )
