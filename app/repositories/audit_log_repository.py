from app.entities.audit_log_entity import AuditLogEntity
from app.repositories.base_repository import BaseRepository


class AuditLogRepository(BaseRepository):
    def create(self, entity: AuditLogEntity) -> AuditLogEntity:
        cursor=self._write("INSERT INTO audit_log (user_id,organization_id,action,target_type,target_id,description,created_at) VALUES (?,?,?,?,?,?,?)",(entity.user_id,entity.organization_id,entity.action,entity.target_type,entity.target_id,entity.description,entity.created_at))
        entity.id=cursor.lastrowid
        return entity

    def find_by_organization(self, organization_id: int, limit: int = 100):
        return [self._entity(r) for r in self._fetch_all("SELECT * FROM audit_log WHERE organization_id=? ORDER BY created_at DESC,id DESC LIMIT ?",(organization_id,limit))]

    @staticmethod
    def _entity(r):
        return AuditLogEntity(id=r["id"],user_id=r["user_id"],organization_id=r["organization_id"],action=r["action"],target_type=r["target_type"],target_id=r["target_id"],description=r["description"],created_at=r["created_at"])
