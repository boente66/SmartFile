from dataclasses import dataclass


@dataclass(slots=True)
class AuditLogEntity:
    id: int | None = None
    user_id: int | None = None
    organization_id: int | None = None
    action: str = ""
    target_type: str | None = None
    target_id: int | None = None
    description: str | None = None
    created_at: str = ""
