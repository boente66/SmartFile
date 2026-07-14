from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class CloudProviderType(StrEnum):
    ONEDRIVE = "ONEDRIVE"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"


class CloudSyncState(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    PENDING_UPLOAD = "PENDING_UPLOAD"
    UPLOADING = "UPLOADING"
    SYNCED = "SYNCED"
    PENDING_DOWNLOAD = "PENDING_DOWNLOAD"
    CONFLICT = "CONFLICT"
    ERROR = "ERROR"
    SYNC_ERROR = "SYNC_ERROR"
    REMOTE_DELETED = "REMOTE_DELETED"
    LOCAL_DELETED = "LOCAL_DELETED"


class CloudJobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    RETRY = "RETRY"
    ERROR = "ERROR"


class CloudOperation(StrEnum):
    UPLOAD = "UPLOAD"
    DOWNLOAD = "DOWNLOAD"
    DELETE = "DELETE"
    RENAME = "RENAME"
    MOVE = "MOVE"
    SYNC = "SYNC"


@dataclass(slots=True)
class CloudAccount:
    id: int | None = None
    provider: str = ""
    email: str | None = None
    display_name: str | None = None
    access_token: str = ""
    refresh_token: str | None = None
    expires_at: str | None = None
    status: str = "ACTIVE"
    created_at: str = ""


@dataclass(slots=True)
class CloudSettings:
    organization_id: int
    cloud_account_id: int | None = None
    sync_mode: str = "LOCAL"
    remote_root_id: str | None = None
    last_sync: str | None = None
    delta_token: str | None = None
    paused: bool = False


@dataclass(slots=True)
class SyncJob:
    id: int | None = None
    document_id: int = 0
    operation: str = CloudOperation.UPLOAD
    provider: str = ""
    status: str = CloudJobStatus.PENDING
    attempts: int = 0
    last_error: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class CloudAuthResult:
    access_token: str = ""
    refresh_token: str | None = None
    expires_at: datetime | None = None
    email: str | None = None
    display_name: str | None = None
    authorization_url: str | None = None
    code_verifier: str | None = None


@dataclass(frozen=True, slots=True)
class RemoteMetadata:
    remote_id: str
    name: str
    size: int = 0
    version: str | None = None
    modified_at: str | None = None
    parent_id: str | None = None
    deleted: bool = False


@dataclass(frozen=True, slots=True)
class CloudUploadRequest:
    local_path: Path
    remote_name: str
    remote_parent_id: str | None = None
    remote_id: str | None = None
