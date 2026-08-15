from __future__ import annotations

import platform
import socket
from datetime import datetime, timezone
from uuid import uuid4

from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.repositories.smartfile_instance_repository import SmartFileInstanceRepository


class SmartFileInstanceService:
    def __init__(self, database, context=None):
        self.database = database; self.context = context
        self.repository = SmartFileInstanceRepository(database=database)

    def local(self, organization_id: int, port: int = 8765) -> SmartFileInstanceEntity:
        existing = self.repository.find_local(organization_id)
        now = self._now()
        if existing:
            existing.current_ip = self.current_ip()
            existing.last_seen_at = now
            return self.repository.save(existing)
        owner = getattr(getattr(self.context, "current_user", None), "id", None)
        return self.repository.save(SmartFileInstanceEntity(
            instance_id=f"SF-{uuid4()}", organization_id=organization_id,
            device_name=platform.node() or "SmartFile", owner_user_id=owner,
            current_ip=self.current_ip(), http_port=self._port(port), enabled=True,
            is_local=True, created_at=now, last_seen_at=now,
        ))

    def configure_local(self, organization_id: int, device_name: str, host: str, port: int, enabled: bool = True):
        if self.context: self.context.require_permission("delivery.configure")
        instance = self.local(organization_id, port)
        instance.device_name = " ".join(device_name.split()) or instance.device_name
        instance.current_ip = self._host(host); instance.http_port = self._port(port); instance.enabled = enabled
        return self.repository.save(instance)

    def register_peer(self, organization_id: int, instance_id: str, device_name: str, host: str, port: int, owner_user_id: int | None = None):
        if self.context: self.context.require_permission("delivery.configure")
        if not instance_id.startswith("SF-") or len(instance_id) > 80:
            raise ValueError("Identidade SmartFile inválida.")
        if owner_user_id is None or self.database.fetch_one(
            """SELECT 1 FROM users user JOIN organization_members member ON member.user_id=user.id
            WHERE user.id=? AND user.is_active=1 AND member.organization_id=? AND member.status='ACTIVE'""",
            (owner_user_id, organization_id),
        ) is None:
            raise ValueError("Associe o peer a um membro ativo da organização.")
        return self.repository.save(SmartFileInstanceEntity(
            instance_id=instance_id, organization_id=organization_id,
            device_name=" ".join(device_name.split()) or "SmartFile remoto",
            owner_user_id=owner_user_id, current_ip=self._host(host),
            http_port=self._port(port), enabled=True, is_local=False,
            created_at=self._now(), last_seen_at=None,
        ))

    @staticmethod
    def current_ip() -> str:
        probe = None
        try:
            probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            probe.connect(("8.8.8.8", 80)); return str(probe.getsockname()[0])
        except (OSError, PermissionError):
            return "127.0.0.1"
        finally:
            if probe is not None:
                probe.close()

    @staticmethod
    def _host(value: str) -> str:
        host = value.strip()
        if not host or any(char in host for char in "/\\?#@"):
            raise ValueError("Endereço da instalação inválido.")
        return host

    @staticmethod
    def _port(value: int) -> int:
        port = int(value)
        if not 1024 <= port <= 65535: raise ValueError("A porta deve estar entre 1024 e 65535.")
        return port

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
