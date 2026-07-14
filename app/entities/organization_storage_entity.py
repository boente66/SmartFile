from dataclasses import dataclass


@dataclass(slots=True)
class OrganizationStorageEntity:
    id: int | None = None
    organization_id: int = 0
    storage_plan_id: int = 0
    quota_bytes: int = 0
    used_bytes: int = 0
    reserved_bytes: int = 0
    created_at: str = ""
    updated_at: str = ""
