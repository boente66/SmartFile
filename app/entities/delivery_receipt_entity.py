from dataclasses import dataclass


@dataclass(slots=True)
class DeliveryAcknowledgementReceiptEntity:
    id: int | None = None
    receipt_uuid: str = ""
    delivery_id: int = 0
    organization_id: int = 0
    signer_user_id: int | None = None
    signer_username: str = ""
    signature_method: str = "DRAWN"
    direction: str = "LOCAL"
    pdf_path: str | None = None
    size: int = 0
    sha256: str = ""
    status: str = "CREATED"
    attempts: int = 0
    next_attempt_at: str | None = None
    last_error: str | None = None
    created_at: str = ""
    sent_at: str | None = None
    received_at: str | None = None

