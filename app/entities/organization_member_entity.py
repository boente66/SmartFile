from dataclasses import dataclass


@dataclass(slots=True)
class OrganizationMemberEntity:
    id: int | None = None
    organization_id: int = 0
    user_id: int = 0
    role: str = "VIEWER"
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""
    invited_by_user_id: int | None = None
    joined_at: str | None = None
    deactivated_at: str | None = None
