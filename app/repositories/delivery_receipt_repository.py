from app.entities.delivery_receipt_entity import DeliveryAcknowledgementReceiptEntity
from app.repositories.base_repository import BaseRepository


class DeliveryAcknowledgementReceiptRepository(BaseRepository):
    COLUMNS = (
        "receipt_uuid", "delivery_id", "organization_id", "signer_user_id",
        "signer_username", "signature_method", "direction", "pdf_path", "size",
        "sha256", "status", "attempts", "next_attempt_at", "last_error",
        "created_at", "sent_at", "received_at",
    )

    def create(self, entity: DeliveryAcknowledgementReceiptEntity):
        values = tuple(getattr(entity, column) for column in self.COLUMNS)
        cursor = self._write(
            f"INSERT INTO delivery_acknowledgement_receipts "
            f"({','.join(self.COLUMNS)}) VALUES ({','.join('?' for _ in values)})",
            values,
        )
        entity.id = cursor.lastrowid
        return entity

    def find_by_id(self, receipt_id: int):
        row = self._fetch_one(
            "SELECT * FROM delivery_acknowledgement_receipts WHERE id=?",
            (receipt_id,),
        )
        return self._entity(row) if row else None

    def find_by_uuid(self, receipt_uuid: str):
        row = self._fetch_one(
            "SELECT * FROM delivery_acknowledgement_receipts WHERE receipt_uuid=?",
            (receipt_uuid,),
        )
        return self._entity(row) if row else None

    def find_by_delivery(self, delivery_id: int):
        row = self._fetch_one(
            "SELECT * FROM delivery_acknowledgement_receipts WHERE delivery_id=?",
            (delivery_id,),
        )
        return self._entity(row) if row else None

    def list_for_organization(self, organization_id: int):
        rows = self._fetch_all(
            "SELECT * FROM delivery_acknowledgement_receipts "
            "WHERE organization_id=? ORDER BY id DESC",
            (organization_id,),
        )
        return [self._entity(row) for row in rows]

    def pending(self, now: str):
        rows = self._fetch_all(
            "SELECT * FROM delivery_acknowledgement_receipts "
            "WHERE direction='LOCAL' AND status IN ('QUEUED','FAILED') "
            "AND attempts < 8 AND (next_attempt_at IS NULL OR next_attempt_at<=?) "
            "ORDER BY id LIMIT 20",
            (now,),
        )
        return [self._entity(row) for row in rows]

    def update(self, receipt_id: int, **values) -> None:
        immutable = {"receipt_uuid", "delivery_id", "organization_id", "direction", "created_at"}
        allowed = set(self.COLUMNS) - immutable
        clean = {key: value for key, value in values.items() if key in allowed}
        if not clean:
            return
        assignments = ",".join(f"{key}=?" for key in clean)
        self._write(
            f"UPDATE delivery_acknowledgement_receipts SET {assignments} WHERE id=?",
            (*clean.values(), receipt_id),
        )

    @classmethod
    def _entity(cls, row):
        return DeliveryAcknowledgementReceiptEntity(
            id=row["id"], **{column: row[column] for column in cls.COLUMNS}
        )

