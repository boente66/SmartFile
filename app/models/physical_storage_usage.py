from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PhysicalStorageUsage:
    ged_bytes: int
    validation_bytes: int
    receipt_bytes: int
    inbox_bytes: int
    installation_total_bytes: int
