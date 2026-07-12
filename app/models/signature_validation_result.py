from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureValidationResult:
    field_name: str
    state: str
    signer_name: str = ""
    issuer: str = ""
    serial_number: str = ""
    certificate_valid_from: str = ""
    certificate_valid_to: str = ""
    signing_time: str = ""
    timestamp_present: bool = False
    integrity_ok: bool = False
    trusted: bool = False
    revoked: bool | None = None
    modified: bool = False
    pades_profile: str = "UNKNOWN"
    visible: bool = False
    details: str = ""
