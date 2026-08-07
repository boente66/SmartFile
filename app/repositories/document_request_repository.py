from __future__ import annotations

from app.entities.document_request_entity import DocumentRequestEntity
from app.repositories.base_repository import BaseRepository


class DocumentRequestRepository(BaseRepository):
    def create(self, entity: DocumentRequestEntity) -> DocumentRequestEntity:
        cursor = self._write(
            """
            INSERT INTO document_requests (
                organization_id, title, description, requested_by_user_id,
                assigned_to_user_id, status, due_at, created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity.organization_id, entity.title, entity.description,
                entity.requested_by_user_id, entity.assigned_to_user_id,
                entity.status, entity.due_at, entity.created_at,
                entity.updated_at, entity.completed_at,
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
                ORDER BY CASE status WHEN 'OVERDUE' THEN 0 WHEN 'OPEN' THEN 1
                         WHEN 'IN_PROGRESS' THEN 2 ELSE 3 END,
                         COALESCE(due_at, '9999-12-31'), id DESC
                """,
                (organization_id,),
            )
        ]

    def find_by_id(self, request_id: int, organization_id: int) -> DocumentRequestEntity | None:
        row = self._fetch_one(
            "SELECT * FROM document_requests WHERE id=? AND organization_id=?",
            (request_id, organization_id),
        )
        return self._entity(row) if row else None

    def update_status(
        self, request_id: int, organization_id: int, status: str,
        updated_at: str, completed_at: str | None,
    ) -> bool:
        return self._write(
            """
            UPDATE document_requests SET status=?, updated_at=?, completed_at=?
            WHERE id=? AND organization_id=?
            """,
            (status, updated_at, completed_at, request_id, organization_id),
        ).rowcount > 0

    def mark_overdue(self, organization_id: int, now: str) -> int:
        return self._write(
            """
            UPDATE document_requests SET status='OVERDUE', updated_at=?
            WHERE organization_id=? AND status IN ('OPEN','IN_PROGRESS')
              AND due_at IS NOT NULL AND due_at < ?
            """,
            (now, organization_id, now),
        ).rowcount

    @staticmethod
    def _entity(row) -> DocumentRequestEntity:
        return DocumentRequestEntity(
            id=row["id"], organization_id=row["organization_id"], title=row["title"],
            description=row["description"], requested_by_user_id=row["requested_by_user_id"],
            assigned_to_user_id=row["assigned_to_user_id"], status=row["status"],
            due_at=row["due_at"], created_at=row["created_at"], updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )
