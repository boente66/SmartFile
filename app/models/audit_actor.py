from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditActor:
    organization_id: int | None
    organization_name: str | None
    organization_uuid: str | None
    user_id: int | None
    username: str
    display_name: str | None
    instance_id: str | None
