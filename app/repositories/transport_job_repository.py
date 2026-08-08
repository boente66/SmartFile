from __future__ import annotations

from datetime import datetime, timezone

from app.repositories.base_repository import BaseRepository
from app.transport.transport_models import (
    TransportJob,
    TransportJobStatus,
    TransportOperation,
)


class TransportJobRepository(BaseRepository):
    """Persistência exclusiva da fila de transporte corporativo."""

    ACTIVE_STATUSES = ("PENDING", "RUNNING", "RETRY")

    def create(self, job: TransportJob) -> TransportJob:
        cursor = self._write(
            """
            INSERT INTO transport_jobs (
                organization_id, document_id, operation, transport_mode,
                status, attempts, last_error, remote_path,
                created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.organization_id, job.document_id, str(job.operation),
                job.transport_mode, str(job.status), job.attempts,
                job.last_error, job.remote_path, job.created_at,
                job.updated_at, job.completed_at,
            ),
        )
        job.id = cursor.lastrowid
        return job

    def find_by_id(self, job_id: int) -> TransportJob | None:
        row = self._fetch_one("SELECT * FROM transport_jobs WHERE id=?", (job_id,))
        return self._entity(row) if row else None

    def find_active(
        self, organization_id: int, document_id: int, operation: str,
    ) -> TransportJob | None:
        row = self._fetch_one(
            """
            SELECT * FROM transport_jobs
            WHERE organization_id=? AND document_id=? AND operation=?
              AND status IN ('PENDING','RUNNING','RETRY')
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id, document_id, operation),
        )
        return self._entity(row) if row else None

    def latest_completed_upload(
        self, organization_id: int, document_id: int,
    ) -> TransportJob | None:
        row = self._fetch_one(
            """
            SELECT * FROM transport_jobs
            WHERE organization_id=? AND document_id=? AND operation='UPLOAD'
              AND status='COMPLETED' AND remote_path IS NOT NULL
            ORDER BY completed_at DESC, id DESC LIMIT 1
            """,
            (organization_id, document_id),
        )
        return self._entity(row) if row else None

    def list_pending(self, organization_id: int, limit: int = 100) -> list[TransportJob]:
        return [
            self._entity(row)
            for row in self._fetch_all(
                """
                SELECT * FROM transport_jobs
                WHERE organization_id=? AND status IN ('PENDING','RETRY')
                ORDER BY attempts, created_at, id LIMIT ?
                """,
                (organization_id, max(1, min(int(limit), 1000))),
            )
        ]

    def next_pending(self, organization_id: int) -> TransportJob | None:
        rows = self.list_pending(organization_id, 1)
        return rows[0] if rows else None

    def mark_running(self, job_id: int) -> bool:
        return self._write(
            """
            UPDATE transport_jobs SET status='RUNNING', attempts=attempts+1,
                last_error=NULL, updated_at=?, completed_at=NULL
            WHERE id=? AND status IN ('PENDING','RETRY')
            """,
            (self._now(), job_id),
        ).rowcount > 0

    def complete(self, job_id: int, remote_path: str | None) -> bool:
        now = self._now()
        return self._write(
            """
            UPDATE transport_jobs SET status='COMPLETED', last_error=NULL,
                remote_path=COALESCE(?, remote_path), updated_at=?, completed_at=?
            WHERE id=? AND status='RUNNING'
            """,
            (remote_path, now, now, job_id),
        ).rowcount > 0

    def fail(self, job_id: int, message: str, max_attempts: int) -> TransportJob:
        current = self.find_by_id(job_id)
        if current is None:
            raise ValueError("Job de transporte não encontrado.")
        status = (
            TransportJobStatus.FAILED
            if current.attempts >= max_attempts
            else TransportJobStatus.RETRY
        )
        completed_at = self._now() if status == TransportJobStatus.FAILED else None
        self._write(
            """
            UPDATE transport_jobs SET status=?, last_error=?, updated_at=?,
                completed_at=? WHERE id=? AND status='RUNNING'
            """,
            (str(status), message, self._now(), completed_at, job_id),
        )
        return self.find_by_id(job_id)

    def fail_definitive(self, job_id: int, message: str) -> TransportJob:
        now = self._now()
        self._write(
            """
            UPDATE transport_jobs SET status='FAILED', last_error=?,
                updated_at=?, completed_at=?
            WHERE id=? AND status='RUNNING'
            """,
            (message, now, now, job_id),
        )
        job = self.find_by_id(job_id)
        if job is None:
            raise ValueError("Job de transporte não encontrado.")
        return job

    def cancel(self, job_id: int, message: str = "Operação cancelada.") -> bool:
        now = self._now()
        return self._write(
            """
            UPDATE transport_jobs SET status='CANCELLED', last_error=?,
                updated_at=?, completed_at=?
            WHERE id=? AND status IN ('PENDING','RUNNING','RETRY')
            """,
            (message, now, now, job_id),
        ).rowcount > 0

    def cancel_uploads(self, organization_id: int, document_id: int) -> int:
        now = self._now()
        return self._write(
            """
            UPDATE transport_jobs SET status='CANCELLED',
                last_error='Documento excluído localmente.', updated_at=?, completed_at=?
            WHERE organization_id=? AND document_id=? AND operation='UPLOAD'
              AND status IN ('PENDING','RUNNING','RETRY')
            """,
            (now, now, organization_id, document_id),
        ).rowcount

    def retry_failed(self, organization_id: int) -> int:
        return self._write(
            """
            UPDATE transport_jobs SET status='RETRY', last_error=NULL,
                updated_at=?, completed_at=NULL
            WHERE organization_id=? AND status='FAILED'
            """,
            (self._now(), organization_id),
        ).rowcount

    def recover_interrupted(self) -> int:
        """Devolve à fila jobs deixados em execução por encerramento abrupto."""
        return self._write(
            """
            UPDATE transport_jobs SET status='RETRY',
                last_error='Operação interrompida; retomada após reinicialização.',
                updated_at=?, completed_at=NULL
            WHERE status='RUNNING'
            """,
            (self._now(),),
        ).rowcount

    def counts(self, organization_id: int) -> dict[str, int]:
        rows = self._fetch_all(
            """
            SELECT status, COUNT(*) AS total FROM transport_jobs
            WHERE organization_id=? GROUP BY status
            """,
            (organization_id,),
        )
        counts = {row["status"]: int(row["total"]) for row in rows}
        return {
            "pending": sum(counts.get(item, 0) for item in self.ACTIVE_STATUSES),
            "failed": counts.get("FAILED", 0),
            "completed": counts.get("COMPLETED", 0),
            "cancelled": counts.get("CANCELLED", 0),
        }

    @staticmethod
    def _entity(row) -> TransportJob:
        return TransportJob(
            id=row["id"], organization_id=row["organization_id"],
            document_id=row["document_id"], operation=row["operation"],
            transport_mode=row["transport_mode"], status=row["status"],
            attempts=row["attempts"], last_error=row["last_error"],
            remote_path=row["remote_path"], created_at=row["created_at"],
            updated_at=row["updated_at"], completed_at=row["completed_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
