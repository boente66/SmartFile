from dataclasses import dataclass
from app.entities.validation_record import ValidationRecord


@dataclass(frozen=True, slots=True)
class DocumentValidationResult:
    record_state: str
    artifact_state: str = "NOT_CHECKED"
    file_integrity: str = "NOT_PROVIDED"
    signature_status: str = "NOT_APPLICABLE"
    trust_status: str = "NOT_APPLICABLE"
    record: ValidationRecord | None = None
    signatures: tuple = ()
    message: str = ""
    matching_records: tuple[ValidationRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicValidationResult:
    """Minimal future DTO; no lookup or publication endpoint is provided."""
    status: str
    validation_code: str
    artifact_type: str
    signature_type: str
    created_at: str
    signed_at: str | None
    integrity_state: str

    @classmethod
    def from_result(cls, result):
        record = result.record
        if record is None:
            raise ValueError("Registro não encontrado.")
        return cls(record.status, record.human_code, record.artifact_type,
                   record.signature_type, record.created_at, record.signed_at,
                   result.artifact_state)
