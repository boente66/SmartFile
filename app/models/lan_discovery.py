from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscoveredSmartFile:
    """Identidade mínima anunciada por uma instalação SmartFile na LAN."""

    instance_id: str
    device_name: str
    host: str
    port: int
    protocol_version: str
    service_name: str = ""
