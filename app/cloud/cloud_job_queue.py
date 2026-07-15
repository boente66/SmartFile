from __future__ import annotations

from datetime import datetime, timezone

from app.cloud.cloud_models import CloudJobStatus, CloudOperation, SyncJob
from app.database.database import Database


class CloudJobQueue:
    def __init__(self, database: Database):
        self.database = database

    def enqueue(self, document_id: int, operation: str, provider: str) -> SyncJob:
        existing = self.database.fetch_one(
            """
            SELECT * FROM sync_jobs WHERE document_id = ? AND operation = ?
                AND status IN ('PENDING', 'RETRY', 'RUNNING') ORDER BY id DESC LIMIT 1
            """,
            (document_id, operation),
        )
        if existing:
            return self._job(existing)
        now = self._now()
        cursor = self.database.execute_query(
            """
            INSERT INTO sync_jobs (
                document_id, operation, provider, status, attempts, created_at, updated_at
            ) VALUES (?, ?, ?, 'PENDING', 0, ?, ?)
            """,
            (document_id, operation, provider, now, now),
        )
        return self.get(cursor.lastrowid)

    def next_pending(self, organization_id: int | None = None) -> SyncJob | None:
        if organization_id is None:
            row = self.database.fetch_one(
                """SELECT * FROM sync_jobs WHERE status IN ('PENDING', 'RETRY')
                   ORDER BY attempts, created_at, id LIMIT 1"""
            )
        else:
            row = self.database.fetch_one(
                """SELECT j.* FROM sync_jobs j JOIN documents d ON d.id=j.document_id
                   WHERE j.status IN ('PENDING','RETRY') AND d.organization_id=?
                   ORDER BY j.attempts,j.created_at,j.id LIMIT 1""",
                (organization_id,),
            )
        return self._job(row) if row else None

    def mark_running(self, job_id: int) -> None:
        self._update(job_id, "RUNNING", None, increment=True)

    def complete(self, job_id: int) -> None:
        self._update(job_id, "COMPLETED", None)

    def retry(self, job_id: int, error: str) -> None:
        job = self.get(job_id)
        self._update(job_id, "ERROR" if job.attempts >= 5 else "RETRY", error)

    def get(self, job_id: int) -> SyncJob:
        row = self.database.fetch_one("SELECT * FROM sync_jobs WHERE id = ?", (job_id,))
        if row is None:
            raise ValueError("Job de sincronização não encontrado.")
        return self._job(row)

    def pending_count(self, organization_id: int | None = None) -> int:
        if organization_id is None:
            row = self.database.fetch_one(
                "SELECT COUNT(*) AS total FROM sync_jobs WHERE status IN ('PENDING', 'RETRY', 'RUNNING')"
            )
        else:
            row = self.database.fetch_one(
                """SELECT COUNT(*) AS total FROM sync_jobs j JOIN documents d ON d.id=j.document_id
                   WHERE j.status IN ('PENDING','RETRY','RUNNING') AND d.organization_id=?""",
                (organization_id,),
            )
        return int(row["total"])

    def _update(self, job_id: int, status: str, error: str | None, increment: bool = False) -> None:
        self.database.execute_query(
            """
            UPDATE sync_jobs SET status = ?, last_error = ?, updated_at = ?,
                attempts = attempts + ? WHERE id = ?
            """,
            (status, error, self._now(), int(increment), job_id),
        )

    @staticmethod
    def _job(row) -> SyncJob:
        return SyncJob(
            id=row["id"], document_id=row["document_id"], operation=row["operation"],
            provider=row["provider"], status=row["status"], attempts=row["attempts"],
            last_error=row["last_error"], created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
