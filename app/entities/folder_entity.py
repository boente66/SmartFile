from dataclasses import dataclass


@dataclass(slots=True)
class FolderEntity:
    id: int | None = None
    organization_id: int = 0
    parent_id: int | None = None
    name: str = ""
    description: str | None = None
    icon: str | None = "folder"
    color: str | None = "#f59e0b"
    created_at: str = ""
    updated_at: str = ""
    status: str = "ACTIVE"
