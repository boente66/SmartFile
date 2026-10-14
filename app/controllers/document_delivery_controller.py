from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from app.services.request_notification_service import RequestNotificationService
from app.system.resources import resource_path

from PyQt6.QtWidgets import QDialog,QFileDialog,QInputDialog,QMessageBox

from app.coordinators.delivery_coordinator import DeliveryCoordinator
from app.services.delivery_basket_service import DeliveryBasketService
from app.services.document_delivery_service import DocumentDeliveryService
from app.services.document_request_service import DocumentRequestService
from app.services.lan_device_discovery_service import LanDeviceDiscoveryService
from app.entities.smartfile_instance_entity import SmartFileInstanceEntity
from app.views.delivery_document_picker_dialog import DeliveryDocumentPickerDialog
from app.views.delivery_workspace_view import DeliveryWorkspaceView
from app.views.delivery_network_dialog import DeliveryNetworkDialog
from app.views.delivery_acknowledgement_dialog import DeliveryAcknowledgementDialog
from app.models.pdf_viewer_context import PDFViewerContext
from app.workers.delivery_send_worker import DeliverySendWorker
from app.workers.file_operation_worker import FileOperationWorker
from app.workers.request_send_worker import RequestSendWorker
from app.workers.lan_discovery_worker import LanConnectionWorker, LanDiscoveryWorker
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION
from app.workers.delivery_receipt_worker import DeliveryReceiptWorker
from app.services.organization_feature_service import OrganizationFeatureService

logger = logging.getLogger(__name__)


class DocumentDeliveryController:
    def __init__(self,workspace,document_service,context,parent=None,pdf_viewer_controller=None,main_view=None):
        self.workspace=workspace; self.documents=document_service; self.context=context; self.parent=parent; self.pdf_viewer=pdf_viewer_controller; self.main_view=main_view
        self.view=DeliveryWorkspaceView(); self.requests=DocumentRequestService(document_service.database,context)
        self.features=OrganizationFeatureService(document_service.database)
        self.service=DocumentDeliveryService(document_service.database,context,document_service)
        self.discovery=LanDeviceDiscoveryService()
        self.basket=DeliveryBasketService(document_service,context); self.coordinator=DeliveryCoordinator(self.service,context,self.view,discovery_service=self.discovery)
        self.worker=None; self.request_worker=None; self.discovery_worker=None; self.connection_workers=set(); self.network_dialog=None; self.receipt_worker=None; self._viewer_delivery_id=None
        self.workspace.register_view("deliveries",self.view); self._connect()
        self.coordinator.notification.connect(self._notification)
        self.coordinator.status_changed.connect(self.view.show_status)
        self.notifications=RequestNotificationService(document_service.database)
        self._request_fingerprint=None
        self._alert_sound=None
        try:
            from PyQt6.QtMultimedia import QSoundEffect
            self._alert_sound=QSoundEffect(self.view)
            self._alert_sound.setSource(QUrl.fromLocalFile(str(resource_path("assets/sounds/request_alert.wav"))))
            self._alert_sound.setLoopCount(1);self._alert_sound.setVolume(.35)
        except ImportError:logger.warning("request.audio.unavailable")
        self._file_worker=None;self._closing=False
        self.notification_timer=QTimer(self.view);self.notification_timer.setInterval(3000)
        self.notification_timer.timeout.connect(self._poll_requests)
        self.coordinator.request_received.connect(self._received_request)
        self.view.request_read.connect(self._mark_request_read)
        self.view.preferences_changed.connect(self.notifications.preferences)
    def _connect(self):
        self.view.create_request_requested.connect(self.create_request); self.view.request_status_requested.connect(self.update_request); self.view.prepare_request_requested.connect(self.prepare_request)
        self.view.select_documents_requested.connect(self.select_documents); self.view.remove_basket_requested.connect(self.remove_basket); self.view.clear_basket_requested.connect(self.clear_basket)
        self.view.send_requested.connect(self.send); self.view.retry_requested.connect(self.retry); self.view.refresh_requested.connect(self.refresh); self.view.configure_requested.connect(self.configure)
        self.view.view_requested.connect(self.view_delivery); self.view.download_requested.connect(self.download); self.view.add_to_ged_requested.connect(self.add_to_ged); self.view.acknowledge_requested.connect(self.acknowledge)
        self.view.receipt_requested.connect(self.view_receipt)
        if self.pdf_viewer:
            self.pdf_viewer.view.document_displayed.connect(self._viewer_displayed)
            self.pdf_viewer.view.context_confirm_requested.connect(self.acknowledge)
    def _require_available(self):
        organization=getattr(self.context,"active_organization",None)
        if organization is None: raise PermissionError("Ative uma organização.")
        self.features.require(organization,"document_requests")
    def activate(self):
        try:self._require_available()
        except Exception as exc:self._error(exc);return
        self.workspace.show_view("deliveries"); self.refresh()
    def organization_changed(self,*_):
        if self._file_worker is not None:self._file_worker.requestInterruption()
        self.coordinator.stop()
        self.notification_timer.stop();self.view.flow.stop_alert();self.view.set_unread(set())
        self._update_request_badge(0)
        self.view.set_requests([],self.context.current_user.id)
        self.view.set_deliveries([],[]);self.view.set_history([])
        self.basket.clear();self.view.set_basket(self.basket.basket)
        self.notifications.scope=None;self._request_fingerprint=None
        if self._alert_sound:self._alert_sound.stop()
        try:
            self._require_available();self.basket.begin();self.start();self.refresh()
        except Exception:
            logger.info("delivery.disabled_for_active_profile")
    def start(self):
        try:
            self._require_available();self._poll_requests();self.notification_timer.start()
            self.coordinator.start(self.documents.active_organization_id)
        except OSError as exc:self.view.show_status(f"Recepção LAN indisponível: {exc}")
        except PermissionError:logger.info("delivery.coordinator.not_started profile=non_business")
    def shutdown(self):
        self._closing=True
        if self._file_worker is not None:
            self._file_worker.requestInterruption();self._file_worker.wait(5000)
        self.notification_timer.stop();self.view.flow.stop_alert()
        if self.worker and self.worker.isRunning():self.worker.requestInterruption();self.worker.wait(5000)
        if self.request_worker and self.request_worker.isRunning():self.request_worker.requestInterruption();self.request_worker.wait(5000)
        if self.receipt_worker and self.receipt_worker.isRunning():self.receipt_worker.requestInterruption();self.receipt_worker.wait(5000)
        self._stop_discovery()
        for worker in tuple(self.connection_workers):
            if worker.isRunning(): worker.requestInterruption(); worker.wait(6000)
        self.connection_workers.clear()
        self.coordinator.stop()
    def refresh(self):
        try:
            self._require_available()
            self._poll_requests()
            org=self.documents.active_organization_id; members=self.requests.list_assignable_members(org); requests=self.requests.list_requests(org)
            self.view.set_permissions(self.context)
            self.view.set_members(members); self.view.set_peers(self.service.instances.repository.list_peers(org)); self.view.set_requests(requests,self.context.current_user.id); self.view.set_basket(self.basket.basket)
            receipts=self.service.receipts.list_for_organization(org)
            self.view.set_deliveries(self.service.deliveries.list_for_organization(org,"OUTGOING"),self.service.deliveries.list_for_organization(org,"INCOMING"),[receipt.delivery_id for receipt in receipts]); self.view.set_history(self.service.history.list(org))
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
        try:
            self.context.require_permission("delivery.create"); self.context.require_permission("document.view")
            organization=self.context.active_organization
            dialog=DeliveryDocumentPickerDialog(
                self.documents.list_documents(),
                self.documents.folder_service.list_folders(self.documents.active_organization_id),
                self.view,
                organization_name=organization.name,
                already_selected=[item.document_id for item in self.basket.basket.items],
            )
            if dialog.exec()==QDialog.DialogCode.Accepted:
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
        try:
            self.service.retry_delivery(delivery_id);self.coordinator.process_pending();self.refresh()
        except Exception as exc:self._error(exc)
    def view_delivery(self,delivery_id):
        delivery=self.service.deliveries.find_by_id(delivery_id);items=self.service.items.list_by_delivery(delivery_id)
        if not delivery or not items:return
        try:
            self.service.authorized_delivery(delivery_id,'delivery.view',recipient_only=True)
            for item in items:self.service._received_item(item.id,'delivery.view')
            pdf_items=[(item.logical_name,Path(item.received_path)) for item in items if item.received_path and Path(item.received_path).suffix.lower()==".pdf"]
            if pdf_items and self.pdf_viewer:
                sender=self.service.users.find_by_id(delivery.sender_user_id)
                receipt=self.service.receipts.find_by_delivery(delivery.id)
                context=PDFViewerContext(
                    kind="DELIVERY_RECEIVED", title="Documento recebido",
                    protocol_number=delivery.protocol_number,
                    sender_name=sender.display_name if sender else None,
                    delivery_id=delivery.id, back_view="deliveries", back_tab="received",
                    items=pdf_items, current_item=0,
                    can_acknowledge=(
                        delivery.status in {"DELIVERED","VIEWED"} and receipt is None
                        and self.context.has_permission("delivery.acknowledge")
                        and delivery.recipient_user_id==self.context.current_user.id
                    ),
                    acknowledged=receipt is not None,
                )
                self._viewer_delivery_id=delivery.id
                self.pdf_viewer.open_document(str(pdf_items[0][1]),context)
            else:
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                path=items[0].received_path
                if path and QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
                    self.service.mark_viewed(delivery.protocol_number,self.context.current_user.id)
                    self.refresh()
                else:
                    raise ValueError("Não foi possível abrir o documento no aplicativo externo.")
        except Exception as exc:self._error(exc)

    def _viewer_displayed(self,_path):
        delivery_id=self._viewer_delivery_id
        if delivery_id is None:return
        self._viewer_delivery_id=None
        delivery=self.service.deliveries.find_by_id(delivery_id)
        if delivery is None:return
        try:
            self.service.mark_viewed(delivery.protocol_number,self.context.current_user.id)
            self.refresh()
        except Exception as exc:self._error(exc)
    def _start_file_operation(self, items, operation, message):
        if self._file_worker is not None:
            QMessageBox.information(self.view,"Arquivos","Aguarde a operação em andamento terminar.");return
        organization_id=self.documents.active_organization_id
        def task(progress,cancelled):
            count=0
            for index,item in enumerate(items,start=1):
                if cancelled():raise InterruptedError()
                progress(int((index-1)*100/len(items)),f"{message}: {index}/{len(items)}")
                operation(item,organization_id,cancelled);count+=1
            return count
        worker=FileOperationWorker(task, audit_actor=self.service.audit.capture(organization_id));self._file_worker=worker
        def current():
            return (not self._closing and self._file_worker is worker
                    and organization_id==getattr(self.context.active_organization,"id",None))
        worker.progress.connect(lambda _value,text:self.view.show_status(text) if current() else None)
        def completed(count):
            if current():
                self.refresh();self.view.show_status(f"{message}: {count} arquivo(s) concluído(s).")
        worker.succeeded.connect(completed)
        worker.failed.connect(lambda text:self._error(text) if current() else None)
        worker.finished.connect(lambda w=worker:self._cleanup_file_worker(w))
        worker.finished.connect(worker.deleteLater);worker.start()

    def _cleanup_file_worker(self,worker):
        if self._file_worker is worker:self._file_worker=None

    def download(self,delivery_id):
        try:self.service.authorized_delivery(delivery_id,"delivery.download",recipient_only=True)
        except Exception as exc:self._error(exc);return
        items=self.service.items.list_by_delivery(delivery_id)
        if not items:return
        directory=QFileDialog.getExistingDirectory(self.view,"Salvar documentos recebidos")
        if directory:
            self._start_file_operation(items,
                lambda item,_org,cancelled:self.service.download_item(item.id,Path(directory)/item.logical_name,cancelled=cancelled),
                "Download")

    def add_to_ged(self,delivery_id):
        try:
            self.service.authorized_delivery(delivery_id,"delivery.download",recipient_only=True)
            items=self.service.items.list_by_delivery(delivery_id)
            if items:
                self._start_file_operation(items,
                    lambda item,org,cancelled:self.service.add_received_to_ged(item.id,organization_id=org,source_type="IMPORT",sync_cloud=True,cancelled=cancelled),
                    "Adição ao GED")
        except Exception as exc:self._error(exc)
    def acknowledge(self,delivery_id):
        if self.receipt_worker is not None:return
        delivery=self.service.deliveries.find_by_id(delivery_id)
        if delivery is None:return
        try:
            items=self.service.items.list_by_delivery(delivery_id)
            sender=self.service.users.find_by_id(delivery.sender_user_id)
            dialog=DeliveryAcknowledgementDialog(delivery.protocol_number,sender.display_name if sender else None,items,self.view)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            signature,method=dialog.signature();dialog.clear_signature()
            worker=DeliveryReceiptWorker(self.service,delivery_id,self.context.current_user.id,signature,method,self.view)
            self.receipt_worker=worker
            worker.succeeded.connect(self._receipt_created)
            worker.failed.connect(lambda message:self._receipt_failed(message))
            worker.finished.connect(lambda worker=worker:self._receipt_done(worker));worker.finished.connect(worker.deleteLater)
            if self.main_view:self.main_view.progress.start("Gerando comprovante de recebimento")
            worker.start()
        except Exception as exc:self._error(exc)

    def _receipt_created(self,receipt):
        if self.main_view:self.main_view.progress.finish("Comprovante de recebimento criado")
        self.view.show_status("Recebimento confirmado. O comprovante será enviado automaticamente.")
        self.coordinator.process_pending();self.refresh()

    def _receipt_failed(self,message):
        if self.main_view:self.main_view.progress.finish("Falha ao gerar comprovante")
        QMessageBox.warning(self.view,"Confirmar recebimento",message)

    def _receipt_done(self,worker):
        if self.receipt_worker is worker:self.receipt_worker=None

    def view_receipt(self,delivery_id):
        try:
            receipt=self.service.open_receipt(delivery_id)
            delivery=self.service.deliveries.find_by_id(delivery_id)
            context=PDFViewerContext(
                kind="DELIVERY_RECEIPT",title="Comprovante de envio" if getattr(receipt,"kind",None)=="SENT" else "Comprovante de recebimento",
                protocol_number=delivery.protocol_number,delivery_id=delivery.id,
                back_view="deliveries",back_tab="received" if delivery.direction=="INCOMING" else "sent",
                items=[("Comprovante de recebimento",Path(receipt.pdf_path))],
                acknowledged=True,
            )
            self._viewer_delivery_id=None
            self.pdf_viewer.open_document(receipt.pdf_path,context)
        except Exception as exc:self._error(exc)
    def configure(self):
        try:
            self.context.require_permission("delivery.configure");organization_id=self.documents.active_organization_id
            dialog=DeliveryNetworkDialog(self.service.instances.local(organization_id),self.service.instances.repository.list_peers(organization_id),self.requests.list_assignable_members(organization_id),self.view)
            self.network_dialog=dialog
            def save_local(values):
                try:
                    self.service.instances.configure_local(organization_id,**values);dialog.set_peers(self.service.instances.repository.list_peers(organization_id));dialog.setWindowTitle("Configuração salva — reinicie a recepção ao fechar")
                except (TypeError, ValueError) as exc:
                    dialog.show_form_error(str(exc))
            def save_peer(values):
                self._save_manual_peer(dialog,organization_id,values)
            def remove_peer(instance_id):
                self.service.instances.repository.delete_peer(organization_id,instance_id);dialog.set_peers(self.service.instances.repository.list_peers(organization_id))
            dialog.save_local_requested.connect(save_local);dialog.save_peer_requested.connect(save_peer);dialog.remove_peer_requested.connect(remove_peer)
            dialog.discover_requested.connect(lambda:self._discover(dialog,organization_id))
            dialog.authorize_requested.connect(lambda device:self._authorize_device(dialog,organization_id,device))
            dialog.test_peer_requested.connect(lambda peer:self._test_peer(dialog,peer))
            dialog.finished.connect(lambda _result:self._network_dialog_closed(dialog))
            dialog.exec(); self.network_dialog=None
            self.coordinator.stop();self.start();self.refresh()
        except Exception as exc:self._error(exc)

    def _discover(self, dialog, organization_id):
        if self.discovery_worker is not None:return
        dialog.set_discovery_state(True,"Procurando SmartFiles na rede local...")
        worker=LanDiscoveryWorker(self.discovery,3.0,self.view);self.discovery_worker=worker
        worker.progress.connect(lambda _value,message:dialog.set_discovery_state(True,message))
        worker.succeeded.connect(lambda devices:self._discovery_succeeded(dialog,organization_id,devices))
        worker.failed.connect(lambda message:self._discovery_failed(dialog,message))
        worker.finished.connect(self._discovery_finished);worker.finished.connect(worker.deleteLater);worker.start()

    def _discovery_succeeded(self,dialog,organization_id,devices):
        if dialog is not self.network_dialog:return
        local=self.service.instances.local(organization_id)
        authorized={
            peer.instance_id:peer
            for peer in self.service.instances.repository.list_peers(organization_id)
        }
        visible=[]
        for device in devices:
            if device.instance_id==local.instance_id:continue
            visible.append(device)
            peer=authorized.get(device.instance_id)
            if peer is not None and device.protocol_version == DELIVERY_PROTOCOL_VERSION:
                candidate=SmartFileInstanceEntity(
                    instance_id=device.instance_id,
                    organization_id=organization_id,
                    device_name=device.device_name,
                    owner_user_id=peer.owner_user_id,
                    current_ip=device.host,
                    http_port=device.port,
                    enabled=peer.enabled,
                    is_local=False,
                )
                dialog.show_connection_pending(
                    device.instance_id,
                    f"Validando identidade de {device.device_name}…",
                )
                self._start_connection_worker(
                    dialog,candidate,
                    lambda _payload,instance_id=device.instance_id:
                    self._verified_discovered_endpoint(dialog,organization_id,instance_id),
                )
        dialog.set_peers(self.service.instances.repository.list_peers(organization_id));dialog.set_discovered(visible)
        message=(f"{len(visible)} SmartFile(s) encontrado(s)." if visible else "Nenhum SmartFile encontrado nesta rede.")
        dialog.set_discovery_state(False,message)

    def _discovery_failed(self,dialog,message):
        if dialog is self.network_dialog:
            dialog.set_discovery_state(False,message)

    def _discovery_finished(self):self.discovery_worker=None

    def _stop_discovery(self):
        worker=self.discovery_worker
        if worker is not None and worker.isRunning():worker.requestInterruption();worker.wait(5000)
        self.discovery_worker=None

    def _network_dialog_closed(self,dialog):
        if dialog is self.network_dialog:self._stop_discovery()

    def _authorize_device(self,dialog,organization_id,device):
        if device.protocol_version != DELIVERY_PROTOCOL_VERSION:
            dialog.show_connection_result(device.instance_id,False,"A versão de protocolo do dispositivo é incompatível.");return
        members=self.requests.list_assignable_members(organization_id)
        if not members:
            dialog.show_connection_result(device.instance_id,False,"Não há membro ativo para associar à instalação.");return
        labels=[member.display_name for member in members]
        selected,ok=QInputDialog.getItem(dialog,"Autorizar SmartFile","Associe esta instalação a um membro:",labels,0,False)
        if not ok:return
        member=members[labels.index(selected)]
        candidate=SmartFileInstanceEntity(instance_id=device.instance_id,organization_id=organization_id,device_name=device.device_name,owner_user_id=member.id,current_ip=device.host,http_port=device.port,is_local=False)
        self._start_connection_worker(dialog,candidate,lambda _payload:self._authorization_verified(dialog,organization_id,device,member.id))

    def _authorization_verified(self,dialog,organization_id,device,owner_user_id):
        if dialog is not self.network_dialog:return
        try:
            self.service.instances.register_peer(organization_id,device.instance_id,device.device_name,device.host,device.port,owner_user_id)
            dialog.set_peers(self.service.instances.repository.list_peers(organization_id));dialog.show_connection_result(device.instance_id,True,"Instalação validada e autorizada com sucesso.")
        except (TypeError,ValueError) as exc:
            dialog.show_connection_result(device.instance_id,False,str(exc))

    def _save_manual_peer(self,dialog,organization_id,values):
        try:
            peer=self.service.instances.register_peer(organization_id,**values)
            dialog.set_peers(self.service.instances.repository.list_peers(organization_id))
            dialog.show_connection_result(
                peer.instance_id,True,"Instalação adicionada ou atualizada."
            )
        except (TypeError,ValueError) as exc:
            message=str(exc)
            if "Identidade SmartFile" in message:
                message=(
                    "SmartFile ID inválido. Use a identificação exibida no outro "
                    "SmartFile, iniciada por SF-."
                )
            dialog.show_form_error(message)
        except Exception as exc:
            logger.error(
                "delivery.peer.manual_save_failed error=%s", type(exc).__name__
            )
            dialog.show_form_error(
                "Não foi possível salvar a instalação. Revise os dados e tente novamente."
            )

    def _verified_discovered_endpoint(self,dialog,organization_id,instance_id):
        if dialog is not self.network_dialog:return
        dialog.set_peers(self.service.instances.repository.list_peers(organization_id))
        dialog.show_connection_result(
            instance_id,True,"Endpoint atualizado após confirmação da identidade HTTP."
        )

    def _test_peer(self,dialog,peer):
        dialog.show_connection_pending(peer.instance_id,"Verificando identidade e versão do protocolo...")
        self._start_connection_worker(dialog,peer,lambda _payload:dialog.show_connection_result(peer.instance_id,True,"Conexão estabelecida e identidade confirmada."))

    def _start_connection_worker(self,dialog,peer,on_success):
        worker=LanConnectionWorker(self.service.instances,peer,self.view);self.connection_workers.add(worker)
        worker.succeeded.connect(lambda payload:self._connection_succeeded(dialog,on_success,payload))
        worker.failed.connect(lambda message:self._connection_failed(dialog,peer.instance_id,message))
        worker.finished.connect(lambda:self.connection_workers.discard(worker));worker.finished.connect(worker.deleteLater);worker.start()
    def _connection_succeeded(self,dialog,on_success,payload):
        if dialog is self.network_dialog:on_success(payload)
    def _connection_failed(self,dialog,instance_id,message):
        if dialog is self.network_dialog:dialog.show_connection_result(instance_id,False,f"Não foi possível conectar ao dispositivo: {message}")
    def _sent(self):self.basket.clear();self.view.show_status("Entrega confirmada pelo destinatário.");self.refresh()
    def _send_failed(self,message):self.view.show_status(f"Destinatário indisponível; entrega mantida na fila: {message}");self.refresh()
    def _worker_done(self):self.worker=None
    def _request_worker_done(self):self.request_worker=None
    def _notification(self,title,message):
        self.view.show_status(message)
    def _poll_requests(self):
        try:
            self._require_available()
            org=self.documents.active_organization_id;user=self.context.current_user.id
            requests=self.requests.list_requests(org)
            new=self.notifications.observe(org,user,requests)
            self.view.set_alert_preferences(self.notifications.sound,self.notifications.animation)
            fingerprint=(org,user,tuple((r.id,r.status,r.title,r.updated_at) for r in requests))
            if fingerprint!=self._request_fingerprint:
                self._request_fingerprint=fingerprint
                self.view.set_requests(requests,user)
            self.view.set_unread(self.notifications.unread)
            self._update_request_badge(len(self.notifications.unread))
            if new:
                if self.notifications.sound and self._alert_sound:self._alert_sound.play()
                if self.notifications.animation:self.view.flow.alert()
        except PermissionError:
            self.notification_timer.stop()
        except Exception:logger.warning("request.notifications.poll_failed",exc_info=True)

    def _received_request(self,organization_id):
        if organization_id==self.documents.active_organization_id:self._poll_requests()

    def _mark_request_read(self,request_id):
        self.notifications.mark_read(request_id)
        self.view.set_unread(self.notifications.unread)
        self._update_request_badge(len(self.notifications.unread))

    def _update_request_badge(self,count):
        sidebar=getattr(self.main_view,"sidebar",None)
        if sidebar and hasattr(sidebar,"set_request_badge"):sidebar.set_request_badge(count)

    def _error(self,exc):QMessageBox.warning(self.view,"Solicitações e Entregas",str(exc))
