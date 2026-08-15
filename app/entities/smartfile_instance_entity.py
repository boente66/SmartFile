from dataclasses import dataclass


@dataclass(slots=True)
class SmartFileInstanceEntity:
    id: int | None = None
    instance_id: str = ""
    organization_id: int = 0
    device_name: str = ""
    owner_user_id: int | None = None
    current_ip: str = "127.0.0.1"
    http_port: int = 8765
    enabled: bool = True
    is_local: bool = False
    created_at: str = ""
    last_seen_at: str | None = None
