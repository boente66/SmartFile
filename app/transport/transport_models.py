from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Callable


class TransportOperation(StrEnum):
    UPLOAD = "UPLOAD"
    DELETE = "DELETE"


class TransportJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    RETRY = "RETRY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ReconciliationStatus(StrEnum):
    RESOLVED = "RESOLVED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


@dataclass(slots=True)
class TransportJob:
    id: int | None = None
    organization_id: int = 0
    document_id: int = 0
    operation: str = TransportOperation.UPLOAD
    transport_mode: str = "NAS"
    transport_target_id: int | None = None
    reconciliation_status: str = ReconciliationStatus.RESOLVED
    status: str = TransportJobStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    remote_path: str | None = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None


@dataclass(frozen=True, slots=True)
class TransportUploadRequest:
    local_path: Path
    remote_name: str
    expected_checksum: str
    progress_callback: Callable[[int, int], None] | None = None
    cancellation_requested: Callable[[], bool] | None = None


@dataclass(frozen=True, slots=True)
class TransportResult:
    success: bool
    message: str
    remote_path: str | None = None
    checksum: str | None = None
    bytes_transferred: int = 0
