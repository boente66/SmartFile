from __future__ import annotations

from datetime import datetime, timezone

from app.entities.transport_target_entity import TransportTargetEntity
from app.repositories.base_repository import BaseRepository


class TransportTargetRepository(BaseRepository):
    """Persiste snapshots físicos; campos de conexão não possuem update."""

    def create(self, target: TransportTargetEntity) -> TransportTargetEntity:
        cursor = self._write(
            """
            INSERT INTO organization_transport_targets (
                organization_id, mode, endpoint, credential_ref, verify_tls,
                fingerprint, status, created_by_user_id, created_at, retired_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target.organization_id, target.mode, target.endpoint,
                target.credential_ref, int(target.verify_tls), target.fingerprint,
                target.status, target.created_by_user_id, target.created_at,
                target.retired_at,
            ),
        )
        created = self.find_by_id(int(cursor.lastrowid), target.organization_id)
        if created is None:
            raise RuntimeError("O destino de transporte não pôde ser recuperado.")
        return created

    def find_by_id(
        self, target_id: int, organization_id: int | None = None,
    ) -> TransportTargetEntity | None:
        query = "SELECT * FROM organization_transport_targets WHERE id=?"
        params: tuple[object, ...] = (target_id,)
        if organization_id is not None:
            query += " AND organization_id=?"
            params += (organization_id,)
        row = self._fetch_one(query, params)
        return self._entity(row) if row else None

    def find_active(self, organization_id: int) -> TransportTargetEntity | None:
        row = self._fetch_one(
            """
            SELECT * FROM organization_transport_targets
            WHERE organization_id=? AND status='ACTIVE'
            ORDER BY id DESC LIMIT 1
            """,
            (organization_id,),
        )
        return self._entity(row) if row else None

    def find_all(self, organization_id: int) -> list[TransportTargetEntity]:
        return [
            self._entity(row) for row in self._fetch_all(
                """
                SELECT * FROM organization_transport_targets
                WHERE organization_id=? ORDER BY id DESC
                """,
                (organization_id,),
            )
        ]

    def retire(self, target_id: int, organization_id: int) -> bool:
        return self._write(
            """
            UPDATE organization_transport_targets
            SET status='RETIRED', retired_at=?
            WHERE id=? AND organization_id=? AND status='ACTIVE'
            """,
            (self._now(), target_id, organization_id),
        ).rowcount > 0

    def count_pending_for_retired(self, organization_id: int) -> int:
        row = self._fetch_one(
            """
            SELECT COUNT(*) AS total FROM transport_jobs j
            JOIN organization_transport_targets t ON t.id=j.transport_target_id
            WHERE j.organization_id=? AND t.status='RETIRED'
              AND j.status IN ('PENDING','RUNNING','RETRY','FAILED')
            """,
            (organization_id,),
        )
        return int(row["total"] if row else 0)

    def is_credential_in_use(self, organization_id: int, reference: str) -> bool:
        active = self._fetch_one(
            """
            SELECT 1 FROM organization_transport_targets
            WHERE organization_id=? AND credential_ref=? AND status='ACTIVE'
            LIMIT 1
            """,
            (organization_id, reference),
        )
        if active:
            return True
        dependent = self._fetch_one(
            """
            SELECT 1 FROM transport_jobs j
            JOIN organization_transport_targets t ON t.id=j.transport_target_id
            WHERE t.organization_id=? AND t.credential_ref=?
              AND (
                j.status IN ('PENDING','RUNNING','RETRY','FAILED')
                OR (
                    j.operation='UPLOAD' AND j.status='COMPLETED'
                    AND NOT EXISTS (
                        SELECT 1 FROM transport_jobs d
                        WHERE d.organization_id=j.organization_id
                          AND d.document_id=j.document_id
                          AND d.transport_target_id=j.transport_target_id
                          AND d.operation='DELETE' AND d.status='COMPLETED'
                    )
                )
              )
            LIMIT 1
            """,
            (organization_id, reference),
        )
        return dependent is not None

    @staticmethod
    def _entity(row) -> TransportTargetEntity:
        return TransportTargetEntity(
            id=row["id"], organization_id=row["organization_id"],
            mode=row["mode"], endpoint=row["endpoint"],
            credential_ref=row["credential_ref"],
            verify_tls=bool(row["verify_tls"]), fingerprint=row["fingerprint"],
            status=row["status"], created_by_user_id=row["created_by_user_id"],
            created_at=row["created_at"], retired_at=row["retired_at"],
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
