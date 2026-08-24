from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class DeliveryReceiptDocument:
    name: str
    size: int
    sha256: str


@dataclass(slots=True)
class DeliveryReceiptRequest:
    output_path: Path
    receipt_uuid: str
    protocol_number: str
    organization_name: str
    sender_name: str
    recipient_name: str
    received_at: str
    confirmed_at: str
    documents: list[DeliveryReceiptDocument]
    signature_image: bytes
    signature_method: str

