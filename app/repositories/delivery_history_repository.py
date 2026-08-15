from app.entities.document_delivery_entity import DeliveryHistoryEntity
from app.repositories.base_repository import BaseRepository


class DeliveryHistoryRepository(BaseRepository):
    def record(self, entity: DeliveryHistoryEntity) -> DeliveryHistoryEntity:
        cursor = self._write(
            "INSERT INTO delivery_history (organization_id,request_id,delivery_id,event_type,actor_user_id,description,created_at) VALUES (?,?,?,?,?,?,?)",
            (entity.organization_id, entity.request_id, entity.delivery_id, entity.event_type, entity.actor_user_id, entity.description, entity.created_at),
        ); entity.id = cursor.lastrowid; return entity

    def list(self, organization_id: int, request_id: int | None = None, delivery_id: int | None = None) -> list[DeliveryHistoryEntity]:
        sql = "SELECT * FROM delivery_history WHERE organization_id=?"; params = [organization_id]
        if request_id is not None: sql += " AND request_id=?"; params.append(request_id)
        if delivery_id is not None: sql += " AND delivery_id=?"; params.append(delivery_id)
        sql += " ORDER BY created_at,id"
        return [DeliveryHistoryEntity(**dict(row)) for row in self._fetch_all(sql, params)]
