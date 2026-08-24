from __future__ import annotations

import http.client
import json
from pathlib import Path
from urllib.parse import quote

from app.errors.delivery_exceptions import DeliveryNetworkError
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION


class DeliveryHttpClient:
    def __init__(self, timeout: float = 20.0): self.timeout = timeout

    def send(self, delivery, metadata: dict, items, progress=None, cancelled=None) -> dict:
        connection = self._connection(delivery.recipient_host, delivery.recipient_port)
        headers = {"Content-Type":"application/json", "X-SmartFile-Instance":delivery.sender_instance_id}
        try:
            connection.request("POST", "/api/v1/deliveries", json.dumps(metadata).encode(), headers)
            self._response(connection)
            total = sum(item.size for item, _path in items) or 1; sent = 0
            for item, path in items:
                if cancelled and cancelled(): raise InterruptedError("Envio cancelado.")
                connection.close(); connection = self._connection(delivery.recipient_host, delivery.recipient_port)
                target = f"/api/v1/deliveries/{quote(delivery.protocol_number)}/items/{quote(item.item_uuid)}"
                connection.putrequest("POST", target)
                connection.putheader("Content-Length", str(item.size)); connection.putheader("Content-Type", "application/octet-stream")
                connection.putheader("X-SmartFile-Instance", delivery.sender_instance_id); connection.endheaders()
                with Path(path).open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        if cancelled and cancelled(): raise InterruptedError("Envio cancelado.")
                        connection.send(chunk); sent += len(chunk)
                        if progress: progress(int(sent * 90 / total), f"Enviando {item.logical_name}")
                self._response(connection)
            connection.close(); connection = self._connection(delivery.recipient_host, delivery.recipient_port)
            connection.request("POST", f"/api/v1/deliveries/{quote(delivery.protocol_number)}/complete", b"{}", headers)
            result = self._response(connection)
            if progress: progress(100, "Entrega verificada pelo destinatário")
            return result
        except InterruptedError: raise
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise DeliveryNetworkError(f"Não foi possível entregar ao SmartFile remoto: {exc}") from exc
        finally: connection.close()

    def send_request(self, peer, payload: dict, sender_instance_id: str) -> dict:
        connection = self._connection(peer.current_ip, peer.http_port)
        try:
            connection.request(
                "POST", "/api/v1/requests", json.dumps(payload).encode(),
                {"Content-Type": "application/json", "X-SmartFile-Instance": sender_instance_id},
            )
            return self._response(connection)
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise DeliveryNetworkError(f"Não foi possível enviar a solicitação: {exc}") from exc
        finally:
            connection.close()

    def identity(
        self, host: str, port: int, *, expected_instance_id: str | None = None,
    ) -> dict:
        connection = self._connection(host, port)
        try:
            connection.request("GET", "/api/v1/identity")
            payload = self._response(connection)
            instance_id = str(payload.get("instance_id", ""))
            protocol = str(payload.get("protocol_version", ""))
            if expected_instance_id and instance_id != expected_instance_id:
                raise DeliveryNetworkError(
                    "A identidade retornada não corresponde ao SmartFile autorizado."
                )
            if protocol != DELIVERY_PROTOCOL_VERSION:
                raise DeliveryNetworkError(
                    f"Versão de protocolo incompatível: {protocol or 'ausente'}."
                )
            return payload
        except DeliveryNetworkError:
            raise
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise DeliveryNetworkError(
                f"Não foi possível conectar ao dispositivo: {exc}"
            ) from exc
        finally:
            connection.close()

    def status(self, delivery) -> dict:
        connection = self._connection(delivery.recipient_host, delivery.recipient_port)
        try:
            connection.request("GET", f"/api/v1/deliveries/{quote(delivery.protocol_number)}", headers={"X-SmartFile-Instance":delivery.sender_instance_id})
            return self._response(connection)
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise DeliveryNetworkError(f"Não foi possível consultar o protocolo remoto: {exc}") from exc
        finally: connection.close()

    def event(self, delivery, event: str, user_id: int) -> dict:
        connection = self._connection(delivery.recipient_host, delivery.recipient_port)
        try:
            body = json.dumps({"user_id": user_id}).encode()
            connection.request("POST", f"/api/v1/deliveries/{quote(delivery.protocol_number)}/{event}", body,
                {"Content-Type":"application/json", "X-SmartFile-Instance":delivery.sender_instance_id})
            return self._response(connection)
        finally: connection.close()

    def send_receipt(self, delivery, receipt, metadata: dict, progress=None) -> dict:
        """Envia o comprovante no sentido destinatário → remetente."""

        headers = {
            "Content-Type": "application/json",
            "X-SmartFile-Instance": delivery.recipient_instance_id,
        }
        connection = self._connection(delivery.recipient_host, delivery.recipient_port)
        try:
            target = (
                f"/api/v1/deliveries/{quote(delivery.protocol_number)}"
                "/acknowledgement"
            )
            connection.request("POST", target, json.dumps(metadata).encode(), headers)
            self._response(connection)
            connection.close()
            connection = self._connection(delivery.recipient_host, delivery.recipient_port)
            content_target = f"{target}/{quote(receipt.receipt_uuid)}/content"
            connection.putrequest("POST", content_target)
            connection.putheader("Content-Length", str(receipt.size))
            connection.putheader("Content-Type", "application/pdf")
            connection.putheader(
                "X-SmartFile-Instance", delivery.recipient_instance_id
            )
            connection.endheaders()
            sent = 0
            with Path(receipt.pdf_path).open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    connection.send(chunk)
                    sent += len(chunk)
                    if progress:
                        progress(
                            min(99, int(sent * 100 / max(receipt.size, 1))),
                            "Enviando comprovante de recebimento",
                        )
            result = self._response(connection)
            if progress:
                progress(100, "Comprovante verificado pelo remetente")
            return result
        except (OSError, TimeoutError, http.client.HTTPException, ValueError) as exc:
            raise DeliveryNetworkError(
                f"Não foi possível enviar o comprovante: {exc}"
            ) from exc
        finally:
            connection.close()

    def _connection(self, host: str, port: int): return http.client.HTTPConnection(host, port, timeout=self.timeout)

    @staticmethod
    def _response(connection) -> dict:
        response = connection.getresponse(); raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024: raise DeliveryNetworkError("Resposta remota excedeu o limite.")
        payload = json.loads(raw.decode() or "{}")
        if response.status >= 400: raise DeliveryNetworkError(str(payload.get("error") or f"HTTP {response.status}"))
        return payload
