from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TransportTargetEntity:
    """Snapshot imutável de um destino físico de transporte."""

    id: int | None = None
    organization_id: int = 0
    mode: str = "NAS"
    endpoint: str = ""
    credential_ref: str | None = None
    verify_tls: bool = True
    fingerprint: str = ""
    status: str = "ACTIVE"
    created_by_user_id: int | None = None
    created_at: str = ""
    retired_at: str | None = None
