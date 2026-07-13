from app.entities.organization_member_entity import OrganizationMemberEntity
from app.repositories.base_repository import BaseRepository


class OrganizationMemberRepository(BaseRepository):
    def create(self, entity: OrganizationMemberEntity) -> OrganizationMemberEntity:
        cursor = self._write(
            """INSERT INTO organization_members
            (organization_id,user_id,role,status,created_at,updated_at,invited_by_user_id,joined_at,deactivated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            self._values(entity),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: OrganizationMemberEntity) -> OrganizationMemberEntity:
        self._write(
            """UPDATE organization_members SET role=?,status=?,updated_at=?,invited_by_user_id=?,
            joined_at=?,deactivated_at=? WHERE id=?""",
            (entity.role,entity.status,entity.updated_at,entity.invited_by_user_id,entity.joined_at,entity.deactivated_at,entity.id),
        )
        return entity

    def find_by_user(self, user_id: int, active_only: bool = True):
        query="SELECT * FROM organization_members WHERE user_id=?"
        if active_only: query += " AND status='ACTIVE'"
        return [self._entity(r) for r in self._fetch_all(query+" ORDER BY id",(user_id,))]

    def find_by_organization(self, organization_id: int, active_only: bool = False):
        query="SELECT * FROM organization_members WHERE organization_id=?"
        if active_only: query += " AND status='ACTIVE'"
        return [self._entity(r) for r in self._fetch_all(query+" ORDER BY role, id",(organization_id,))]

    def find(self, organization_id: int, user_id: int):
        row=self._fetch_one("SELECT * FROM organization_members WHERE organization_id=? AND user_id=?",(organization_id,user_id))
        return self._entity(row) if row else None

    def count_active_owners(self, organization_id: int) -> int:
        return int(self._fetch_one("SELECT COUNT(*) total FROM organization_members WHERE organization_id=? AND role='OWNER' AND status='ACTIVE'",(organization_id,))["total"])

    def count_active(self, organization_id: int) -> int:
        return int(self._fetch_one("SELECT COUNT(*) total FROM organization_members WHERE organization_id=? AND status='ACTIVE'",(organization_id,))["total"])

    @staticmethod
    def _values(e):
        return (e.organization_id,e.user_id,e.role,e.status,e.created_at,e.updated_at,e.invited_by_user_id,e.joined_at,e.deactivated_at)

    @staticmethod
    def _entity(r):
        return OrganizationMemberEntity(id=r["id"],organization_id=r["organization_id"],user_id=r["user_id"],role=r["role"],status=r["status"],created_at=r["created_at"],updated_at=r["updated_at"],invited_by_user_id=r["invited_by_user_id"],joined_at=r["joined_at"],deactivated_at=r["deactivated_at"])
