from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OrganizationFeatureSettingEntity:
    organization_id: int
    feature_code: str
    enabled: bool
    updated_by_user_id: int | None = None
    updated_at: str = ""
