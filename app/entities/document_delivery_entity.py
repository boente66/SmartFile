from dataclasses import dataclass


@dataclass(slots=True)
class DocumentDeliveryEntity:
    id: int | None = None
    delivery_uuid: str = ""
    protocol_number: str = ""
    organization_id: int = 0
    request_id: int | None = None
    sender_user_id: int | None = None
    recipient_user_id: int | None = None
    sender_instance_id: str = ""
    recipient_instance_id: str = ""
    recipient_host: str = ""
    recipient_port: int = 8765
    direction: str = "OUTGOING"
    message: str | None = None
    status: str = "CREATED"
    attempts: int = 0
    next_attempt_at: str | None = None
    last_error: str | None = None
    created_at: str = ""
    queued_at: str | None = None
    sent_at: str | None = None
    delivered_at: str | None = None
    viewed_at: str | None = None
    viewed_by_user_id: int | None = None
    acknowledged_at: str | None = None
    completed_at: str | None = None
    cancelled_at: str | None = None


@dataclass(slots=True)
class DocumentDeliveryItemEntity:
    id: int | None = None
    item_uuid: str = ""
    delivery_id: int = 0
    document_id: int | None = None
    logical_name: str = ""
    size: int = 0
    sha256: str = ""
    transfer_status: str = "PENDING"
    received_path: str | None = None
    sent_at: str | None = None
    received_at: str | None = None


@dataclass(slots=True)
class DeliveryHistoryEntity:
    id: int | None = None
    organization_id: int = 0
    request_id: int | None = None
    delivery_id: int | None = None
    event_type: str = ""
    actor_user_id: int | None = None
    description: str = ""
    created_at: str = ""
