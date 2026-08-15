from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import QDialog,QFileDialog,QMessageBox

from app.coordinators.delivery_coordinator import DeliveryCoordinator
from app.services.delivery_basket_service import DeliveryBasketService
from app.services.document_delivery_service import DocumentDeliveryService
from app.services.document_request_service import DocumentRequestService
from app.views.delivery_document_picker_dialog import DeliveryDocumentPickerDialog
from app.views.delivery_workspace_view import DeliveryWorkspaceView
from app.views.delivery_network_dialog import DeliveryNetworkDialog
from app.workers.delivery_send_worker import DeliverySendWorker
from app.workers.request_send_worker import RequestSendWorker


class DocumentDeliveryController:
    def __init__(self,workspace,document_service,context,parent=None):
        self.workspace=workspace; self.documents=document_service; self.context=context; self.parent=parent
        self.view=DeliveryWorkspaceView(); self.requests=DocumentRequestService(document_service.database,context)
        self.service=DocumentDeliveryService(document_service.database,context,document_service)
        self.basket=DeliveryBasketService(document_service,context); self.coordinator=DeliveryCoordinator(self.service,context,self.view)
        self.worker=None; self.request_worker=None; self.workspace.register_view("deliveries",self.view); self._connect()
        self.coordinator.notification.connect(self._notification)
    def _connect(self):
        self.view.create_request_requested.connect(self.create_request); self.view.request_status_requested.connect(self.update_request); self.view.prepare_request_requested.connect(self.prepare_request)
        self.view.select_documents_requested.connect(self.select_documents); self.view.remove_basket_requested.connect(self.remove_basket); self.view.clear_basket_requested.connect(self.clear_basket)
        self.view.send_requested.connect(self.send); self.view.retry_requested.connect(self.retry); self.view.refresh_requested.connect(self.refresh); self.view.configure_requested.connect(self.configure)
        self.view.view_requested.connect(self.view_delivery); self.view.download_requested.connect(self.download); self.view.add_to_ged_requested.connect(self.add_to_ged); self.view.acknowledge_requested.connect(self.acknowledge)
    def activate(self):self.workspace.show_view("deliveries"); self.refresh()
    def organization_changed(self,*_):
        self.coordinator.stop()
        self.basket.begin()
        self.start();self.refresh()
    def start(self):
        try:self.coordinator.start(self.documents.active_organization_id)
        except OSError as exc:self.view.show_status(f"Recepção LAN indisponível: {exc}")
    def shutdown(self):
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait(5000)
        if self.request_worker and self.request_worker.isRunning():self.request_worker.requestInterruption();self.request_worker.wait(5000)
        self.coordinator.stop()
    def refresh(self):
        try:
            org=self.documents.active_organization_id; members=self.requests.list_assignable_members(org); requests=self.requests.list_requests(org)
            self.view.set_permissions(self.context)
            self.view.set_members(members); self.view.set_peers(self.service.instances.repository.list_peers(org)); self.view.set_requests(requests,self.context.current_user.id); self.view.set_basket(self.basket.basket)
            self.view.set_deliveries(self.service.deliveries.list_for_organization(org,"OUTGOING"),self.service.deliveries.list_for_organization(org,"INCOMING")); self.view.set_history(self.service.history.list(org))
        except Exception as exc:self._error(exc)
    def create_request(self,values):
        try:
            created=self.requests.create(self.documents.active_organization_id,**values)
            peer=next((item for item in self.service.instances.repository.list_peers(self.documents.active_organization_id) if item.owner_user_id==created.assigned_to_user_id),None)
            if peer is not None:
                self.request_worker=RequestSendWorker(self.coordinator,created.id,peer,self.view)
                self.request_worker.succeeded.connect(lambda _:self.view.show_status("Solicitação entregue ao responsável."))
                self.request_worker.failed.connect(lambda message:self.view.show_status(f"Solicitação criada localmente; responsável offline: {message}"))
                self.request_worker.finished.connect(self._request_worker_done);self.request_worker.finished.connect(self.request_worker.deleteLater);self.request_worker.start()
            self.refresh()
        except Exception as exc:self._error(exc)
    def update_request(self,request_id,status):
        try:self.requests.set_status(self.documents.active_organization_id,request_id,status);self.refresh()
        except Exception as exc:self._error(exc)
    def select_documents(self):
        dialog=DeliveryDocumentPickerDialog(self.documents.list_documents(),self.documents.folder_service.list_folders(self.documents.active_organization_id),self.view)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            try:
                for document_id in dialog.selected_document_ids():
                    self.basket.add_document(document_id)
                    if self.basket.basket.request_id:
                        self.requests.link_document(self.documents.active_organization_id,self.basket.basket.request_id,document_id)
                self.view.set_basket(self.basket.basket)
            except Exception as exc:self._error(exc)
    def prepare_request(self,request_id):
        try:
            organization_id=self.documents.active_organization_id
            request=self.requests.repository.find_by_id(request_id,organization_id)
            if request is None:raise ValueError("Solicitação não encontrada.")
            if request.status not in {"ATTENDED","OVERDUE"}:raise ValueError("Marque a solicitação como ATENDIDA antes de preparar a entrega.")
            if not request.origin_instance_id:raise ValueError("A solicitação não possui uma instalação de origem registrada.")
            self.basket.begin(request_id=request.id,recipient_user_id=request.requested_by_user_id)
            for document_id in self.requests.linked_document_ids(organization_id,request.id):self.basket.add_document(document_id)
            self.view.set_basket(self.basket.basket);self.view.select_delivery_target(request.requested_by_user_id,request.origin_instance_id)
            self.view.show_status("Cesta vinculada à solicitação. Selecione os documentos e envie.")
        except Exception as exc:self._error(exc)
    def remove_basket(self,document_id):self.basket.remove_document(document_id);self.view.set_basket(self.basket.basket)
    def clear_basket(self):self.basket.clear();self.view.set_basket(self.basket.basket)
    def send(self,values):
        if self.worker is not None:return
        try:
            self.basket.basket.recipient_user_id=values["recipient_user_id"]
            delivery=self.service.create(self.documents.active_organization_id,self.basket.basket,values["recipient_instance_id"],values["message"]);self.service.queue(delivery.id)
            self.worker=DeliverySendWorker(self.coordinator,delivery.id,self.view);self.worker.progress.connect(lambda value,message:self.view.show_status(f"{message} {value}%"));self.worker.succeeded.connect(lambda _:self._sent());self.worker.failed.connect(lambda message:self._send_failed(message));self.worker.finished.connect(self._worker_done);self.worker.finished.connect(self.worker.deleteLater);self.worker.start();self.refresh()
        except Exception as exc:self._error(exc)
    def retry(self,delivery_id):
        delivery=self.service.deliveries.find_by_id(delivery_id)
        if delivery:self.service.deliveries.update(delivery_id,next_attempt_at=self.service._now(),status="QUEUED",attempts=0,last_error=None);self.coordinator.process_pending();self.refresh()
    def view_delivery(self,delivery_id):
        delivery=self.service.deliveries.find_by_id(delivery_id);items=self.service.items.list_by_delivery(delivery_id)
        if not delivery or not items:return
        try:
            self.service.mark_viewed(delivery.protocol_number,self.context.current_user.id)
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(items[0].received_path))
            self.refresh()
        except Exception as exc:self._error(exc)
    def download(self,delivery_id):
        items=self.service.items.list_by_delivery(delivery_id)
        if not items:return
        directory=QFileDialog.getExistingDirectory(self.view,"Salvar documentos recebidos")
        if directory:
            try:
                for item in items:self.service.download_item(item.id,Path(directory)/item.logical_name)
            except Exception as exc:self._error(exc)
    def add_to_ged(self,delivery_id):
        items=self.service.items.list_by_delivery(delivery_id)
        try:
            for item in items:self.service.add_received_to_ged(item.id,organization_id=self.documents.active_organization_id,source_type="IMPORT",sync_cloud=True)
            self.refresh()
        except Exception as exc:self._error(exc)
    def acknowledge(self,delivery_id):
        delivery=self.service.deliveries.find_by_id(delivery_id)
        try:self.service.acknowledge(delivery.protocol_number,self.context.current_user.id);self.refresh()
        except Exception as exc:self._error(exc)
    def configure(self):
        try:
            self.context.require_permission("delivery.configure");organization_id=self.documents.active_organization_id
            dialog=DeliveryNetworkDialog(self.service.instances.local(organization_id),self.service.instances.repository.list_peers(organization_id),self.requests.list_assignable_members(organization_id),self.view)
            def save_local(values):
                self.service.instances.configure_local(organization_id,**values);dialog.set_peers(self.service.instances.repository.list_peers(organization_id));dialog.setWindowTitle("Configuração salva — reinicie a recepção ao fechar")
            def save_peer(values):
                self.service.instances.register_peer(organization_id,**values);dialog.set_peers(self.service.instances.repository.list_peers(organization_id))
            def remove_peer(instance_id):
                self.service.instances.repository.delete_peer(organization_id,instance_id);dialog.set_peers(self.service.instances.repository.list_peers(organization_id))
            dialog.save_local_requested.connect(save_local);dialog.save_peer_requested.connect(save_peer);dialog.remove_peer_requested.connect(remove_peer);dialog.exec()
            self.coordinator.stop();self.start();self.refresh()
        except Exception as exc:self._error(exc)
    def _sent(self):self.basket.clear();self.view.show_status("Entrega confirmada pelo destinatário.");self.refresh()
    def _send_failed(self,message):self.view.show_status(f"Destinatário indisponível; entrega mantida na fila: {message}");self.refresh()
    def _worker_done(self):self.worker=None
    def _request_worker_done(self):self.request_worker=None
    def _notification(self,title,message):
        self.view.show_status(message);QMessageBox.information(self.view,title,message)
    def _error(self,exc):QMessageBox.warning(self.view,"Solicitações e Entregas",str(exc))
