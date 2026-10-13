from dataclasses import dataclass
from enum import StrEnum


class ArtifactType(StrEnum):
    SIGNED_DOCUMENT = "SIGNED_DOCUMENT"
    VISUAL_SIGNED_DOCUMENT = "VISUAL_SIGNED_DOCUMENT"
    UNSIGNED_REGISTERED_DOCUMENT = "UNSIGNED_REGISTERED_DOCUMENT"
    DELIVERY_RECEIPT = "DELIVERY_RECEIPT"


class SignatureType(StrEnum):
    NONE = "NONE"
    VISUAL_HANDWRITTEN = "VISUAL_HANDWRITTEN"
    A1_PADES = "A1_PADES"


@dataclass(frozen=True, slots=True)
class ValidationRecord:
    id: int
    organization_id: int
    public_token: str
    human_code: str
    artifact_type: str
    signature_type: str
    logical_name_snapshot: str
    created_at: str
    status: str = "PENDING"
    document_id: int | None = None
    delivery_id: int | None = None
    receipt_id: int | None = None
    protocol_snapshot: str | None = None
    artifact_storage_ref: str | None = None
    artifact_size: int | None = None
    final_sha256: str | None = None
    created_by_user_id: int | None = None
    signed_at: str | None = None
    payload_version: int = 1
    revoked_at: str | None = None
    revoked_by_user_id: int | None = None
    revocation_reason: str | None = None
    publication_mode: str = "LOCAL_ONLY"
    publication_status: str = "NOT_PUBLISHED"
    locator_mode: str = "LOCAL"
    base_url_snapshot: str | None = None
    canonical_mime_type: str = "application/pdf"
