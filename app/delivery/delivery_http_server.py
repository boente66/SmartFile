from __future__ import annotations

import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from app.errors.delivery_exceptions import DeliveryError

logger = logging.getLogger(__name__)


class DeliveryHttpServer:
    def __init__(self, host: str, port: int, service):
        self.host=host; self.port=port; self.service=service; self._server=None; self._thread=None

    def start(self) -> int:
        if self._server: return self._server.server_port
        service = self.service
        class Handler(BaseHTTPRequestHandler):
            server_version = "SmartFileDelivery/1.0"
            def setup(self):
                super().setup()
                self.connection.settimeout(30.0)
            def do_POST(self):
                try: self._post()
                except (DeliveryError, ValueError, KeyError, json.JSONDecodeError) as exc: self._json(400, {"error":str(exc)})
                except (TimeoutError, OSError) as exc: self._json(408, {"error":f"Transferência interrompida: {exc}"})
                except Exception:
                    logger.exception("delivery.http.server.failed"); self._json(500, {"error":"Falha interna ao processar entrega."})
            def do_GET(self):
                try:
                    protocol = self._protocol_path()
                    self._validate_peer(protocol)
                    self._json(200, service.status_payload(protocol))
                except (DeliveryError, ValueError) as exc: self._json(404, {"error":str(exc)})
            def _post(self):
                path = urlparse(self.path).path
                if path == "/api/v1/requests":
                    payload = self._body_json()
                    self._validate_instance(str(payload.get("origin_instance_id", "")))
                    request = service.receive_request(payload)
                    self._json(201, {"request_uuid": request.request_uuid})
                    return
                if path == "/api/v1/deliveries":
                    payload = self._body_json(); self._validate_instance(str(payload.get("sender_instance_id", "")))
                    delivery = service.receive_metadata(payload); self._json(201, {"protocol_number":delivery.protocol_number}); return
                item_match = re.fullmatch(r"/api/v1/deliveries/([^/]+)/items/([^/]+)", path)
                if item_match:
                    protocol, item_uuid = map(unquote, item_match.groups()); self._validate_peer(protocol)
                    size = int(self.headers.get("Content-Length", "-1")); service.receive_item(protocol, item_uuid, self.rfile, size)
                    self._json(200, {"status":"VERIFIED"}); return
                event_match = re.fullmatch(r"/api/v1/deliveries/([^/]+)/(complete|viewed|acknowledge)", path)
                if event_match:
                    protocol, event = map(unquote, event_match.groups()); self._validate_peer(protocol)
                    if event == "complete": delivery=service.complete_incoming(protocol)
                    else:
                        user_id=int(self._body_json()["user_id"])
                        service.mark_viewed(protocol,user_id) if event=="viewed" else service.acknowledge(protocol,user_id)
                        delivery=service.deliveries.find_by_protocol(protocol)
                    self._json(200, service.status_payload(delivery.protocol_number)); return
                self._json(404, {"error":"Endpoint não encontrado."})
            def _protocol_path(self):
                match=re.fullmatch(r"/api/v1/deliveries/([^/]+)",urlparse(self.path).path)
                if not match: raise ValueError("Endpoint inválido.")
                return unquote(match.group(1))
            def _validate_peer(self, protocol):
                delivery=service.deliveries.find_by_protocol(protocol)
                if delivery is None: raise ValueError("Protocolo não encontrado.")
                self._validate_instance(delivery.sender_instance_id)
            def _validate_instance(self, expected):
                if self.headers.get("X-SmartFile-Instance") != expected: raise ValueError("Identidade da instalação remetente inválida.")
            def _body_json(self):
                length=int(self.headers.get("Content-Length","0"))
                if length < 0 or length > 1024*1024: raise ValueError("Payload de metadados excede o limite.")
                return json.loads(self.rfile.read(length).decode() or "{}")
            def _json(self,status,payload):
                body=json.dumps(payload).encode(); self.send_response(status); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, fmt, *args): logger.info("delivery.http %s", fmt % args)
        self._server=ThreadingHTTPServer((self.host,self.port),Handler); self._server.daemon_threads=True
        self._thread=threading.Thread(target=self._server.serve_forever,name="smartfile-delivery-http",daemon=True); self._thread.start()
        return self._server.server_port

    def stop(self) -> None:
        if self._server: self._server.shutdown(); self._server.server_close()
        if self._thread: self._thread.join(timeout=5)
        self._server=None; self._thread=None
