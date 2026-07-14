from dataclasses import dataclass


@dataclass(slots=True)
class StorageReservationEntity:
    id: int | None = None
    operation_id: str = ""
    organization_id: int = 0
    size_bytes: int = 0
    status: str = "RESERVED"
    created_at: str = ""
    expires_at: str = ""
    committed_at: str | None = None
    released_at: str | None = None
