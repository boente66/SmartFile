from __future__ import annotations

import ipaddress
import logging
import socket
import threading
import time
from collections.abc import Callable

from app.models.lan_discovery import DiscoveredSmartFile
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION

logger = logging.getLogger(__name__)


class LanDiscoveryError(RuntimeError):
    """Falha de domínio ao anunciar ou descobrir SmartFiles na rede local."""


class LanDeviceDiscoveryService:
    """Descobre e anuncia endpoints locais via mDNS/DNS-SD.

    A descoberta só produz candidatos. A autorização permanece uma decisão
    explícita coordenada pela camada de aplicação.
    """

    SERVICE_TYPE = "_smartfile._tcp.local."

    def __init__(self, zeroconf_factory=None, browser_factory=None) -> None:
        self._zeroconf_factory = zeroconf_factory
        self._browser_factory = browser_factory
        self._advertiser = None
        self._service_info = None
        self._lock = threading.RLock()

    def discover(
        self,
        timeout: float = 3.0,
        *,
        cancelled: Callable[[], bool] | None = None,
    ) -> list[DiscoveredSmartFile]:
        zeroconf, browser_class, state_added, state_updated = self._runtime()
        try:
            client = zeroconf()
        except Exception as exc:
            raise LanDiscoveryError(
                f"Não foi possível iniciar a descoberta local: {exc}"
            ) from exc
        found: dict[str, DiscoveredSmartFile] = {}
        lock = threading.Lock()

        def on_state_change(zc, service_type, name, state_change) -> None:
            if state_change not in {state_added, state_updated}:
                return
            try:
                info = zc.get_service_info(service_type, name, timeout=700)
                device = self.normalize_service_info(name, info)
                if device is not None:
                    with lock:
                        found[device.instance_id] = device
            except Exception:
                logger.warning("delivery.discovery.resolve_failed service=%s", name, exc_info=True)

        browser = None
        deadline = time.monotonic() + max(0.1, min(float(timeout), 15.0))
        try:
            browser = browser_class(client, self.SERVICE_TYPE, handlers=[on_state_change])
            while time.monotonic() < deadline:
                if cancelled and cancelled():
                    break
                time.sleep(0.05)
            with lock:
                return sorted(found.values(), key=lambda item: item.device_name.casefold())
        except Exception as exc:
            raise LanDiscoveryError(f"Não foi possível procurar SmartFiles na rede: {exc}") from exc
        finally:
            if browser is not None:
                try:
                    browser.cancel()
                except Exception:
                    logger.debug("delivery.discovery.browser_cleanup_failed", exc_info=True)
            try:
                client.close()
            except Exception:
                logger.debug("delivery.discovery.client_cleanup_failed", exc_info=True)

    def start_advertising(self, local_instance) -> None:
        """Publica somente identidade, nome, protocolo e porta do servidor ativo."""

        self.stop_advertising()
        host = self._local_ipv4(local_instance.current_ip)
        if host is None:
            logger.info("delivery.discovery.advertise_skipped invalid_local_ip=%s", local_instance.current_ip)
            return
        zeroconf, _browser, _added, _updated = self._runtime()
        from zeroconf import ServiceInfo

        instance_label = self._service_label(local_instance.device_name, local_instance.instance_id)
        info = ServiceInfo(
            type_=self.SERVICE_TYPE,
            name=f"{instance_label}.{self.SERVICE_TYPE}",
            addresses=[socket.inet_aton(host)],
            port=int(local_instance.http_port),
            properties={
                b"instance_id": local_instance.instance_id.encode("utf-8"),
                b"device_name": local_instance.device_name.encode("utf-8"),
                b"protocol_version": DELIVERY_PROTOCOL_VERSION.encode("ascii"),
            },
            server=f"{socket.gethostname().replace('.', '-')}.local.",
        )
        advertiser = zeroconf()
        try:
            advertiser.register_service(info, allow_name_change=True)
        except Exception as exc:
            advertiser.close()
            raise LanDiscoveryError(f"Não foi possível anunciar o SmartFile na rede: {exc}") from exc
        with self._lock:
            self._advertiser = advertiser
            self._service_info = info
        logger.info(
            "delivery.discovery.advertising instance_id=%s endpoint=%s:%s",
            local_instance.instance_id, host, local_instance.http_port,
        )

    def stop_advertising(self) -> None:
        with self._lock:
            advertiser, info = self._advertiser, self._service_info
            self._advertiser = self._service_info = None
        if advertiser is None:
            return
        try:
            if info is not None:
                advertiser.unregister_service(info)
        except Exception:
            logger.debug("delivery.discovery.unregister_failed", exc_info=True)
        finally:
            advertiser.close()

    @classmethod
    def normalize_service_info(cls, service_name: str, info) -> DiscoveredSmartFile | None:
        if info is None:
            return None
        properties = {
            cls._decode(key): cls._decode(value)
            for key, value in dict(getattr(info, "properties", {}) or {}).items()
        }
        instance_id = properties.get("instance_id", "").strip()
        device_name = " ".join(properties.get("device_name", "").split())
        protocol = properties.get("protocol_version", "").strip()
        port = int(getattr(info, "port", 0) or 0)
        addresses = cls._addresses(info)
        host = next((item for item in addresses if cls._local_ipv4(item)), None)
        if (
            not instance_id.startswith("SF-")
            or len(instance_id) > 80
            or not device_name
            or len(device_name) > 120
            or not protocol
            or len(protocol) > 20
            or not 1024 <= port <= 65535
            or host is None
        ):
            return None
        return DiscoveredSmartFile(
            instance_id=instance_id,
            device_name=device_name,
            host=host,
            port=port,
            protocol_version=protocol,
            service_name=service_name,
        )

    @staticmethod
    def _decode(value) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    @staticmethod
    def _addresses(info) -> list[str]:
        parser = getattr(info, "parsed_scoped_addresses", None) or getattr(info, "parsed_addresses", None)
        if callable(parser):
            try:
                return [str(item) for item in parser()]
            except Exception:
                return []
        return []

    @staticmethod
    def _local_ipv4(value: str) -> str | None:
        try:
            address = ipaddress.ip_address(str(value).split("%", 1)[0])
        except ValueError:
            return None
        if address.version != 4 or address.is_unspecified or address.is_multicast:
            return None
        return str(address)

    @staticmethod
    def _service_label(device_name: str, instance_id: str) -> str:
        clean = "-".join(device_name.replace(".", " ").split())[:40] or "SmartFile"
        suffix = instance_id.removeprefix("SF-")[:8]
        return f"{clean}-{suffix}"

    def _runtime(self):
        try:
            from zeroconf import IPVersion, ServiceBrowser, ServiceStateChange, Zeroconf
        except ImportError as exc:
            raise LanDiscoveryError(
                "A descoberta automática não está disponível nesta instalação. Use a configuração manual."
            ) from exc
        factory = self._zeroconf_factory or (lambda: Zeroconf(ip_version=IPVersion.V4Only))
        browser = self._browser_factory or ServiceBrowser
        return factory, browser, ServiceStateChange.Added, ServiceStateChange.Updated
