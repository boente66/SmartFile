from __future__ import annotations

import ipaddress
import platform
import re
import socket
from datetime import datetime, timezone
from uuid import uuid4

from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.repositories.smartfile_instance_repository import SmartFileInstanceRepository


class SmartFileInstanceService:
    INSTANCE_ID_PATTERN = re.compile(r"^SF-[A-Za-z0-9][A-Za-z0-9._:-]{0,76}$")

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
        clean_instance_id = str(instance_id or "").strip()
        if self.INSTANCE_ID_PATTERN.fullmatch(clean_instance_id) is None:
            raise ValueError("Identidade SmartFile inválida.")
        if owner_user_id is None or self.database.fetch_one(
            """SELECT 1 FROM users user JOIN organization_members member ON member.user_id=user.id
            WHERE user.id=? AND user.is_active=1 AND member.organization_id=? AND member.status='ACTIVE'""",
            (owner_user_id, organization_id),
        ) is None:
            raise ValueError("Associe o peer a um membro ativo da organização.")
        return self.repository.save(SmartFileInstanceEntity(
            instance_id=clean_instance_id, organization_id=organization_id,
            device_name=" ".join(str(device_name or "").split()) or "SmartFile remoto",
            owner_user_id=owner_user_id, current_ip=self._host(host),
            http_port=self._port(port), enabled=True, is_local=False,
            created_at=self._now(), last_seen_at=None,
        ))

    def apply_discovery(self, organization_id: int, device, *, identity=None):
        """Atualiza um endpoint mDNS somente após prova HTTP da identidade."""

        existing = self.repository.find_by_instance_id(device.instance_id)
        if existing is None or existing.organization_id != organization_id or existing.is_local:
            return None
        if not isinstance(identity, dict):
            return None
        if (
            str(identity.get("instance_id", "")).strip() != existing.instance_id
            or str(identity.get("protocol_version", "")).strip()
            != self._protocol_version()
        ):
            return None
        existing.device_name = " ".join(device.device_name.split()) or existing.device_name
        existing.current_ip = self._host(device.host)
        existing.http_port = self._port(device.port)
        existing.last_seen_at = self._now()
        return self.repository.save(existing)

    def test_connection(self, peer) -> dict:
        """Valida endpoint, UUID e versão do protocolo; porta aberta não basta."""

        from app.delivery.delivery_http_client import DeliveryHttpClient

        result = DeliveryHttpClient(timeout=5.0).identity(
            peer.current_ip, peer.http_port, expected_instance_id=peer.instance_id,
        )
        persisted = self.repository.find_by_instance_id(peer.instance_id)
        if (
            persisted is not None
            and persisted.organization_id == peer.organization_id
            and not persisted.is_local
        ):
            persisted.device_name = (
                " ".join(str(peer.device_name or "").split())
                or persisted.device_name
            )
            persisted.current_ip = self._host(peer.current_ip)
            persisted.http_port = self._port(peer.http_port)
            persisted.last_seen_at = self._now()
            self.repository.save(persisted)
        return result

    @staticmethod
    def current_ip() -> str:
        candidates: list[str] = []
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
                # A conexão UDP apenas consulta a rota local; nenhum pacote é enviado.
                probe.connect(("224.0.0.251", 5353))
                candidates.append(str(probe.getsockname()[0]))
        except (OSError, PermissionError):
            pass
        try:
            candidates.extend(
                str(item[4][0])
                for item in socket.getaddrinfo(
                    socket.gethostname(), None, socket.AF_INET, socket.SOCK_DGRAM,
                )
            )
        except (OSError, socket.gaierror):
            pass
        for candidate in candidates:
            if SmartFileInstanceService._lan_ipv4(candidate):
                return candidate
        # Endereço não roteável: o anúncio mDNS será deliberadamente ignorado.
        return "0.0.0.0"

    @staticmethod
    def _host(value: str) -> str:
        host = str(value or "").strip()
        if not host or any(char in host for char in "/\\?#@"):
            raise ValueError("Endereço da instalação inválido.")
        try:
            ipaddress.ip_address(host.split("%", 1)[0])
        except ValueError:
            if (
                len(host) > 253
                or not re.fullmatch(
                    r"(?=.{1,253}\.?$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
                    r"[A-Za-z0-9])?\.)*[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}"
                    r"[A-Za-z0-9])?\.?",
                    host,
                )
            ):
                raise ValueError("Endereço da instalação inválido.")
        return host

    @staticmethod
    def _lan_ipv4(value: str) -> bool:
        try:
            address = ipaddress.ip_address(str(value).split("%", 1)[0])
        except ValueError:
            return False
        return bool(
            address.version == 4
            and not address.is_loopback
            and not address.is_unspecified
            and not address.is_multicast
        )

    @staticmethod
    def _protocol_version() -> str:
        from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION

        return DELIVERY_PROTOCOL_VERSION

    @staticmethod
    def _port(value: int) -> int:
        port = int(value)
        if not 1024 <= port <= 65535: raise ValueError("A porta deve estar entre 1024 e 65535.")
        return port

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
