from app.entities.document_delivery_entity import DocumentDeliveryEntity, DocumentDeliveryItemEntity
from app.repositories.base_repository import BaseRepository


class DocumentDeliveryRepository(BaseRepository):
    COLUMNS = ("delivery_uuid","protocol_number","organization_id","request_id","sender_user_id","recipient_user_id","sender_instance_id","recipient_instance_id","recipient_host","recipient_port","direction","message","status","attempts","next_attempt_at","last_error","created_at","queued_at","sent_at","delivered_at","viewed_at","viewed_by_user_id","acknowledged_at","completed_at","cancelled_at")

    def create(self, entity: DocumentDeliveryEntity) -> DocumentDeliveryEntity:
        values = tuple(getattr(entity, name) for name in self.COLUMNS)
        cursor = self._write(f"INSERT INTO document_deliveries ({','.join(self.COLUMNS)}) VALUES ({','.join('?' for _ in values)})", values)
        entity.id = cursor.lastrowid
        return entity

    def find_by_id(self, delivery_id: int) -> DocumentDeliveryEntity | None:
        row = self._fetch_one("SELECT * FROM document_deliveries WHERE id=?", (delivery_id,))
        return self._entity(row) if row else None

    def find_by_protocol(self, protocol: str) -> DocumentDeliveryEntity | None:
        row = self._fetch_one("SELECT * FROM document_deliveries WHERE protocol_number=?", (protocol,))
        return self._entity(row) if row else None

    def list_for_organization(self, organization_id: int, direction: str | None = None) -> list[DocumentDeliveryEntity]:
        sql = "SELECT * FROM document_deliveries WHERE organization_id=?"
        params = [organization_id]
        if direction:
            sql += " AND direction=?"; params.append(direction)
        sql += " ORDER BY id DESC"
        return [self._entity(row) for row in self._fetch_all(sql, params)]

    def pending(self, now: str) -> list[DocumentDeliveryEntity]:
        return [self._entity(row) for row in self._fetch_all(
            "SELECT * FROM document_deliveries WHERE direction='OUTGOING' AND status='QUEUED' AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id LIMIT 20", (now,)
        )]

    def update(self, delivery_id: int, **values) -> None:
        allowed = set(self.COLUMNS) - {"delivery_uuid", "protocol_number", "organization_id", "direction", "created_at"}
        clean = {key: value for key, value in values.items() if key in allowed}
        if not clean: return
        self._write(f"UPDATE document_deliveries SET {','.join(f'{key}=?' for key in clean)} WHERE id=?", (*clean.values(), delivery_id))

    @classmethod
    def _entity(cls, row) -> DocumentDeliveryEntity:
        return DocumentDeliveryEntity(id=row["id"], **{name: row[name] for name in cls.COLUMNS})


class DocumentDeliveryItemRepository(BaseRepository):
    def create(self, entity: DocumentDeliveryItemEntity) -> DocumentDeliveryItemEntity:
        cursor = self._write(
            """INSERT INTO document_delivery_items
            (item_uuid,delivery_id,document_id,logical_name,size,sha256,transfer_status,received_path,sent_at,received_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (entity.item_uuid, entity.delivery_id, entity.document_id, entity.logical_name, entity.size,
             entity.sha256, entity.transfer_status, entity.received_path, entity.sent_at, entity.received_at),
        ); entity.id = cursor.lastrowid; return entity

    def list_by_delivery(self, delivery_id: int) -> list[DocumentDeliveryItemEntity]:
        return [self._entity(row) for row in self._fetch_all("SELECT * FROM document_delivery_items WHERE delivery_id=? ORDER BY id", (delivery_id,))]

    def find_by_uuid(self, item_uuid: str) -> DocumentDeliveryItemEntity | None:
        row = self._fetch_one("SELECT * FROM document_delivery_items WHERE item_uuid=?", (item_uuid,))
        return self._entity(row) if row else None

    def update_received(self, item_uuid: str, status: str, path: str | None, received_at: str | None) -> None:
        self._write("UPDATE document_delivery_items SET transfer_status=?, received_path=?, received_at=? WHERE item_uuid=?", (status, path, received_at, item_uuid))

    def update_sent(self, item_uuid: str, sent_at: str) -> None:
        self._write("UPDATE document_delivery_items SET transfer_status='VERIFIED', sent_at=? WHERE item_uuid=?", (sent_at, item_uuid))

    @staticmethod
    def _entity(row) -> DocumentDeliveryItemEntity:
        return DocumentDeliveryItemEntity(**{key: row[key] for key in ("id","item_uuid","delivery_id","document_id","logical_name","size","sha256","transfer_status","received_path","sent_at","received_at")})
