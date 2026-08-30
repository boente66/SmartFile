from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RemoteMountEntity:
    id: int | None = None
    organization_id: int = 0
    cloud_account_id: int = 0
    provider: str = ""
    remote_root_id: str = ""
    remote_root_name: str = ""
    logical_mount_name: str = ""
    collection_key: str = ""
    status: str = "ACTIVE"
    created_at: str = ""
    last_scan_at: str | None = None
    last_error: str | None = None


@dataclass(slots=True)
class RemoteCatalogNodeEntity:
    id: int | None = None
    organization_id: int = 0
    mount_id: int = 0
    cloud_account_id: int = 0
    provider: str = ""
    remote_id: str = ""
    remote_parent_id: str | None = None
    logical_path: str = ""
    node_type: str = "FILE"
    name: str = ""
    mime_type: str | None = None
    size: int = 0
    modified_at: str | None = None
    provider_hash: str | None = None
    version: str | None = None
    status: str = "ACTIVE"
    discovered_at: str = ""
    last_seen_at: str = ""


@dataclass(slots=True)
class LogicalCloudObjectEntity:
    id: int | None = None
    organization_id: int = 0
    collection_key: str = ""
    logical_path: str = ""
    logical_name: str = ""
    object_type: str = "FILE"
    identity_state: str = "UNRELATED"
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class CloudReplicaEntity:
    id: int | None = None
    organization_id: int = 0
    logical_object_id: int = 0
    mount_id: int = 0
    catalog_node_id: int = 0
    cloud_account_id: int = 0
    provider: str = ""
    remote_id: str = ""
    provider_hash: str | None = None
    verified_sha256: str | None = None
    replica_status: str = "PRESENT"
    created_at: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class MulticloudPlanEntity:
    id: int | None = None
    organization_id: int = 0
    plan_uuid: str = ""
    status: str = "DRAFT"
    created_at: str = ""
    authorized_at: str | None = None
    authorized_by_user_id: int | None = None
    completed_at: str | None = None
    last_error: str | None = None


@dataclass(slots=True)
class MulticloudPlanActionEntity:
    id: int | None = None
    organization_id: int = 0
    plan_id: int = 0
    action_type: str = "REPLICATE_FILE"
    source_replica_id: int | None = None
    target_mount_id: int = 0
    target_parent_remote_id: str | None = None
    logical_object_id: int | None = None
    risk_level: str = "LOW"
    reason: str = ""
    status: str = "PROPOSED"
    idempotency_key: str = ""
    created_at: str = ""
    completed_at: str | None = None
    last_error: str | None = None
