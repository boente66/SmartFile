from dataclasses import dataclass


@dataclass(slots=True)
class StoragePlanEntity:
    id: int | None = None
    code: str = ""
    name: str = ""
    quota_bytes: int = 0
    description: str | None = None
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
