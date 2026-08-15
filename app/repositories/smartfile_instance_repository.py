from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.repositories.base_repository import BaseRepository


class SmartFileInstanceRepository(BaseRepository):
    def save(self, entity: SmartFileInstanceEntity) -> SmartFileInstanceEntity:
        existing = self.find_by_instance_id(entity.instance_id)
        if existing:
            self._write(
                "UPDATE smartfile_instances SET device_name=?, owner_user_id=?, current_ip=?, http_port=?, enabled=?, last_seen_at=? WHERE instance_id=? AND organization_id=?",
                (entity.device_name, entity.owner_user_id, entity.current_ip, entity.http_port, int(entity.enabled), entity.last_seen_at, entity.instance_id, entity.organization_id),
            )
            return self.find_by_instance_id(entity.instance_id)
        cursor = self._write(
            """INSERT INTO smartfile_instances
            (instance_id,organization_id,device_name,owner_user_id,current_ip,http_port,enabled,is_local,created_at,last_seen_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (entity.instance_id, entity.organization_id, entity.device_name, entity.owner_user_id,
             entity.current_ip, entity.http_port, int(entity.enabled), int(entity.is_local), entity.created_at, entity.last_seen_at),
        )
        entity.id = cursor.lastrowid
        return entity

    def find_local(self, organization_id: int) -> SmartFileInstanceEntity | None:
        row = self._fetch_one("SELECT * FROM smartfile_instances WHERE organization_id=? AND is_local=1", (organization_id,))
        return self._entity(row) if row else None

    def find_by_instance_id(self, instance_id: str) -> SmartFileInstanceEntity | None:
        row = self._fetch_one("SELECT * FROM smartfile_instances WHERE instance_id=?", (instance_id,))
        return self._entity(row) if row else None

    def list_peers(self, organization_id: int) -> list[SmartFileInstanceEntity]:
        return [self._entity(row) for row in self._fetch_all(
            "SELECT * FROM smartfile_instances WHERE organization_id=? AND is_local=0 AND enabled=1 ORDER BY device_name", (organization_id,)
        )]

    def delete_peer(self, organization_id: int, instance_id: str) -> bool:
        return self._write(
            "UPDATE smartfile_instances SET enabled=0 WHERE organization_id=? AND instance_id=? AND is_local=0",
            (organization_id, instance_id),
        ).rowcount > 0

    @staticmethod
    def _entity(row) -> SmartFileInstanceEntity:
        return SmartFileInstanceEntity(
            id=row["id"], instance_id=row["instance_id"], organization_id=row["organization_id"],
            device_name=row["device_name"], owner_user_id=row["owner_user_id"], current_ip=row["current_ip"],
            http_port=row["http_port"], enabled=bool(row["enabled"]), is_local=bool(row["is_local"]),
            created_at=row["created_at"], last_seen_at=row["last_seen_at"],
        )
