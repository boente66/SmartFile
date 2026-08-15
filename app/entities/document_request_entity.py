from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class DocumentRequestEntity:
    id: int | None = None
    request_uuid: str = ""
    organization_id: int = 0
    title: str = ""
    description: str | None = None
    requested_by_user_id: int | None = None
    assigned_to_user_id: int | None = None
    status: str = "OPEN"
    due_at: str | None = None
    created_at: str = ""
    updated_at: str = ""
    started_at: str | None = None
    attended_at: str | None = None
    delivered_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None
    origin_instance_id: str | None = None
    target_instance_id: str | None = None

    def is_overdue(self, now: datetime | None = None) -> bool:
        if not self.due_at or self.status in {"DELIVERED", "COMPLETED", "CANCELLED"}:
            return False
        try:
            due = datetime.fromisoformat(self.due_at)
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            return due < (now or datetime.now(timezone.utc))
        except ValueError:
            return False
