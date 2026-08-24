from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.delivery.delivery_http_client import DeliveryHttpClient
from app.delivery.delivery_http_server import DeliveryHttpServer
from app.workers.delivery_queue_worker import DeliveryQueueWorker

logger=logging.getLogger(__name__)


class DeliveryCoordinator(QObject):
    notification=pyqtSignal(str,str); status_changed=pyqtSignal(str)
    def __init__(self, service, context=None, parent=None, client=None, discovery_service=None):
        super().__init__(parent); self.service=service; self.context=context; self.client=client or DeliveryHttpClient(); self.server=None; self.discovery_service=discovery_service
        self.service.notification_callback = self.notification.emit; self.queue_worker=None
        self.timer=QTimer(self); self.timer.setInterval(30_000); self.timer.timeout.connect(self.process_pending)

    def start(self, organization_id: int, host: str="0.0.0.0", port: int|None=None, *, background: bool=True) -> int:
        local=self.service.instances.local(organization_id,8765 if port is None else max(port,1024))
        selected_port=local.http_port if port is None else port
        self.server=DeliveryHttpServer(host,selected_port,self.service); actual=self.server.start()
        if actual != local.http_port: local.http_port=actual; self.service.instances.repository.save(local)
        if self.discovery_service is not None:
            local.http_port = actual
            try:
                self.discovery_service.start_advertising(local)
            except Exception:
                logger.warning("delivery.discovery.advertising_failed", exc_info=True)
        if background:
            self.timer.start(); self.process_pending()
        return actual

    def stop(self):
        self.timer.stop()
        if self.discovery_service is not None:
            self.discovery_service.stop_advertising()
        if self.queue_worker and self.queue_worker.isRunning():
            self.queue_worker.requestInterruption();self.queue_worker.wait(25_000)
        if self.server: self.server.stop(); self.server=None

    def send_once(self, delivery_id: int, progress=None, cancelled=None):
        delivery=self.service.deliveries.find_by_id(delivery_id)
        if delivery is None: raise ValueError("Entrega não encontrada.")
        self.service.mark_sending(delivery_id)
        items=[]
        for item in self.service.items.list_by_delivery(delivery_id):
            document=self.service.document_service.get_document(item.document_id)
            if document is None: raise ValueError("Documento da entrega não encontrado.")
            items.append((item,Path(document.path)))
        try:
            result=self.client.send(delivery,self.service.metadata(delivery_id),items,progress,cancelled)
            self.service.mark_delivered(delivery_id); return result
        except Exception as exc:
            self.service.queue(delivery_id,str(exc)); raise

    def process_pending(self):
        if self.queue_worker is not None:
            return
        self.queue_worker=DeliveryQueueWorker(self,self)
        self.queue_worker.failed.connect(lambda message:logger.warning("delivery.queue.failed %s",message))
        self.queue_worker.finished.connect(self._queue_finished)
        self.queue_worker.finished.connect(self.queue_worker.deleteLater)
        self.queue_worker.start()

    def _queue_finished(self):
        self.queue_worker=None
        self.status_changed.emit("Fila de entregas atualizada.")

    def process_pending_sync(self, cancelled=None):
        self.process_pending_requests()
        for delivery in self.service.deliveries.pending(datetime.now(timezone.utc).isoformat()):
            if cancelled and cancelled():
                return
            try: self.send_once(delivery.id,cancelled=cancelled)
            except Exception: logger.warning("delivery.retry.failed protocol=%s",delivery.protocol_number,exc_info=True)
        self.process_pending_receipts(cancelled)
        self.refresh_outgoing_statuses()

    def process_pending_receipts(self, cancelled=None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        for receipt in self.service.receipts.pending(now):
            if cancelled and cancelled():
                return
            try:
                self.send_receipt_once(receipt.id)
            except Exception:
                logger.warning(
                    "delivery.receipt.retry_failed receipt=%s",
                    receipt.receipt_uuid, exc_info=True,
                )

    def send_receipt_once(self, receipt_id: int, progress=None):
        receipt = self.service.receipts.find_by_id(receipt_id)
        if receipt is None:
            raise ValueError("Comprovante não encontrado.")
        delivery = self.service.deliveries.find_by_id(receipt.delivery_id)
        if delivery is None:
            raise ValueError("Entrega do comprovante não encontrada.")
        self.service.mark_receipt_sending(receipt_id)
        try:
            result = self.client.send_receipt(
                delivery, receipt, self.service.receipt_metadata(receipt_id), progress
            )
            self.service.mark_receipt_sent(receipt_id)
            return result
        except Exception as exc:
            self.service.queue_receipt(receipt_id, str(exc))
            raise

    def send_request(self, request_id: int, peer) -> dict:
        request = self.service.requests.find_by_id(request_id)
        if request is None:
            raise ValueError("Solicitação não encontrada.")
        local = self.service.instances.local(request.organization_id)
        self.service.requests.update_route(
            request.id, request.organization_id, local.instance_id, peer.instance_id,
        )
        payload = self.service.request_payload(request.id)
        result = self.client.send_request(peer, payload, local.instance_id)
        self.service.mark_request_dispatched(request.id)
        return result

    def process_pending_requests(self) -> None:
        organization = getattr(getattr(self.context, "active_organization", None), "id", None)
        if not organization:
            return
        for request in self.service.requests.pending_remote(organization):
            peer = self.service.instances.repository.find_by_instance_id(
                request.target_instance_id
            )
            if peer is None or not peer.enabled:
                continue
            try:
                self.send_request(request.id, peer)
            except Exception:
                logger.info(
                    "delivery.request.remote_unavailable request_uuid=%s",
                    request.request_uuid,
                )

    def refresh_outgoing_statuses(self) -> None:
        organization = getattr(getattr(self.context, "active_organization", None), "id", None)
        if not organization:
            return
        outgoing = self.service.deliveries.list_for_organization(organization, "OUTGOING")
        for delivery in outgoing:
            if delivery.status not in {"DELIVERED", "VIEWED"}:
                continue
            try:
                self.refresh_remote(delivery.id)
            except Exception:
                logger.info("delivery.status.remote_unavailable protocol=%s", delivery.protocol_number)

    def refresh_remote(self, delivery_id: int):
        delivery=self.service.deliveries.find_by_id(delivery_id); payload=self.client.status(delivery); self.service.apply_remote_status(delivery_id,payload); return payload
