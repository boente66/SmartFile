from datetime import datetime, timezone

from app.entities.audit_log_entity import AuditLogEntity
from app.repositories.audit_log_repository import AuditLogRepository


class AuditService:
    def __init__(self, database):
        self.repository=AuditLogRepository(database=database)

    def record(self, action, *, user_id=None, organization_id=None, target_type=None, target_id=None, description=None):
        return self.repository.create(AuditLogEntity(user_id=user_id,organization_id=organization_id,action=action,target_type=target_type,target_id=target_id,description=description,created_at=datetime.now(timezone.utc).isoformat()))

    def list_for_organization(self, organization_id, limit=100):
        return self.repository.find_by_organization(organization_id,limit)
