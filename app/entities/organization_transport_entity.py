from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrganizationTransportEntity:
    organization_id: int
    mode: str = "LOCAL"
    endpoint: str | None = None
    enabled: bool = False
    verify_tls: bool = True
    updated_by_user_id: int | None = None
    updated_at: str = ""
