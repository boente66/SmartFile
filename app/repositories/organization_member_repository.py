from app.entities.organization_member_entity import OrganizationMemberEntity
from app.repositories.base_repository import BaseRepository


class OrganizationMemberRepository(BaseRepository):
    def create(self, entity):
        cursor=self._write("INSERT INTO organization_members (organization_id,user_id,role,status,created_at,updated_at) VALUES (?,?,?,?,?,?)",(entity.organization_id,entity.user_id,entity.role,entity.status,entity.created_at,entity.updated_at)); entity.id=cursor.lastrowid; return entity
    def find_by_user(self,user_id:int):
        rows=self._fetch_all("SELECT * FROM organization_members WHERE user_id=? AND status='ACTIVE' ORDER BY id",(user_id,)); return [self._entity(r) for r in rows]
    def find(self,organization_id:int,user_id:int):
        r=self._fetch_one("SELECT * FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,user_id)); return self._entity(r) if r else None
    @staticmethod
    def _entity(r):
        return OrganizationMemberEntity(id=r["id"],organization_id=r["organization_id"],user_id=r["user_id"],role=r["role"],status=r["status"],created_at=r["created_at"],updated_at=r["updated_at"])
