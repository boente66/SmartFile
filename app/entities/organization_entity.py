from dataclasses import dataclass


@dataclass(slots=True)
class OrganizationEntity:
    id: int | None = None
    name: str = ""
    description: str | None = None
    slug: str = ""
    icon: str | None = "organization"
    color: str | None = "#2563eb"
    created_at: str = ""
    updated_at: str = ""
    is_default: bool = False
    status: str = "ACTIVE"
