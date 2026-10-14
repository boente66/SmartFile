from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuditLogEntity:
    id: int | None = None
    user_id: int | None = None
    organization_id: int | None = None
    action: str = ""
    target_type: str | None = None
    target_id: int | None = None
    description: str | None = None
    created_at: str = ""
    event_uuid: str | None = None
    actor_username: str | None = None
    actor_name: str | None = None
    organization_name: str | None = None
    organization_uuid: str | None = None
    instance_id: str | None = None
    document_uuid: str | None = None
    document_name: str | None = None
    source_type: str | None = None
    sha256_before: str | None = None
    sha256_after: str | None = None
    details_json: str | None = None
