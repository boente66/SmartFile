from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DocumentRequestEntity:
    id: int | None = None
    organization_id: int = 0
    title: str = ""
    description: str | None = None
    requested_by_user_id: int | None = None
    assigned_to_user_id: int | None = None
    status: str = "OPEN"
    due_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None
