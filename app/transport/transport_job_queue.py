from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.transport_job_repository import TransportJobRepository
from app.transport.transport_models import TransportJob, TransportOperation


class TransportJobQueue:
    """Fila persistente e independente da CloudJobQueue."""

    def __init__(self, database):
        self.repository = TransportJobRepository(database=database)

    def enqueue_upload(self, organization_id: int, document_id: int) -> TransportJob:
        return self._enqueue(
            organization_id, document_id, TransportOperation.UPLOAD, None,
        )

    def enqueue_delete(
        self, organization_id: int, document_id: int, remote_path: str,
    ) -> TransportJob:
        return self._enqueue(
            organization_id, document_id, TransportOperation.DELETE, remote_path,
        )

    def _enqueue(
        self, organization_id: int, document_id: int,
        operation: TransportOperation, remote_path: str | None,
    ) -> TransportJob:
        existing = self.repository.find_active(
            organization_id, document_id, str(operation),
        )
        if existing is not None:
            return existing
        now = datetime.now(timezone.utc).isoformat()
        return self.repository.create(TransportJob(
            organization_id=organization_id,
            document_id=document_id,
            operation=operation,
            transport_mode="NAS",
            remote_path=remote_path,
            created_at=now,
            updated_at=now,
        ))

    def next_pending(self, organization_id: int) -> TransportJob | None:
        return self.repository.next_pending(organization_id)

    def list_pending(self, organization_id: int, limit: int = 100) -> list[TransportJob]:
        return self.repository.list_pending(organization_id, limit)

    def get(self, job_id: int) -> TransportJob:
        job = self.repository.find_by_id(job_id)
        if job is None:
            raise ValueError("Job de transporte não encontrado.")
        return job
