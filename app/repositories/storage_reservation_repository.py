from app.entities.storage_reservation_entity import StorageReservationEntity
from app.repositories.base_repository import BaseRepository


class StorageReservationRepository(BaseRepository):
    def create(self, entity: StorageReservationEntity) -> StorageReservationEntity:
        cursor = self._write(
            """INSERT INTO storage_reservations
               (operation_id, organization_id, size_bytes, status, created_at, expires_at, committed_at, released_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (entity.operation_id, entity.organization_id, entity.size_bytes, entity.status,
             entity.created_at, entity.expires_at, entity.committed_at, entity.released_at),
        )
        entity.id = cursor.lastrowid
        return entity

    def find_by_operation(self, operation_id: str) -> StorageReservationEntity | None:
        row = self._fetch_one("SELECT * FROM storage_reservations WHERE operation_id=?", (operation_id,))
        return self._entity(row) if row else None

    def update_status(self, operation_id: str, expected: str, status: str, timestamp_column: str, now: str) -> bool:
        if timestamp_column not in {"committed_at", "released_at"}:
            raise ValueError("Coluna de timestamp inválida.")
        return self._write(
            f"UPDATE storage_reservations SET status=?, {timestamp_column}=? WHERE operation_id=? AND status=?",
            (status, now, operation_id, expected),
        ).rowcount == 1

    def find_expired(self, now: str) -> list[StorageReservationEntity]:
        return [self._entity(row) for row in self._fetch_all(
            "SELECT * FROM storage_reservations WHERE status='RESERVED' AND expires_at<=?", (now,)
        )]

    @staticmethod
    def _entity(row) -> StorageReservationEntity:
        return StorageReservationEntity(
            id=row["id"], operation_id=row["operation_id"], organization_id=row["organization_id"],
            size_bytes=int(row["size_bytes"]), status=row["status"], created_at=row["created_at"],
            expires_at=row["expires_at"], committed_at=row["committed_at"], released_at=row["released_at"],
        )
