from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox,QFormLayout,QFrame,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QPushButton,QTabWidget,QTextEdit,QVBoxLayout,QWidget)

from app.ui.icon_provider import IconProvider


class DeliveryWorkspaceView(QWidget):
    create_request_requested=pyqtSignal(dict); request_status_requested=pyqtSignal(int,str)
    prepare_request_requested=pyqtSignal(int)
    select_documents_requested=pyqtSignal(); remove_basket_requested=pyqtSignal(int); clear_basket_requested=pyqtSignal(); send_requested=pyqtSignal(dict)
    retry_requested=pyqtSignal(int); view_requested=pyqtSignal(int); download_requested=pyqtSignal(int); add_to_ged_requested=pyqtSignal(int); acknowledge_requested=pyqtSignal(int); receipt_requested=pyqtSignal(int)
    configure_requested=pyqtSignal(); refresh_requested=pyqtSignal()
    def __init__(self):
        super().__init__(); self.setObjectName("deliveryWorkspace"); self._can_acknowledge=False; self._setup()
    def _setup(self):
        root=QVBoxLayout(self); root.setContentsMargins(22,18,22,18)
        header=QHBoxLayout(); titles=QVBoxLayout(); title=QLabel("Solicitações e Entregas"); title.setObjectName("deliveryTitle"); titles.addWidget(title); titles.addWidget(QLabel("Solicite, prepare, envie e acompanhe documentos por protocolo.")); header.addLayout(titles); header.addStretch()
        self.configure=QPushButton("Configurar LAN"); IconProvider.apply(self.configure,"provider_settings"); self.configure.clicked.connect(self.configure_requested.emit)
        refresh=QPushButton("Atualizar"); IconProvider.apply(refresh,"cloud_sync"); refresh.clicked.connect(self.refresh_requested.emit); header.addWidget(self.configure); header.addWidget(refresh); root.addLayout(header)
        self.tabs=QTabWidget(); root.addWidget(self.tabs,1)
        self.overview_list=QListWidget(); self.tabs.addTab(self._list_panel(self.overview_list),"Caixa de entrada")
        self.tabs.addTab(self._requests_tab(),"Solicitações recebidas")
        self.created_list=QListWidget(); self.tabs.addTab(self._list_panel(self.created_list),"Criadas por mim")
        self.attending_list=QListWidget(); self.tabs.addTab(self._list_panel(self.attending_list),"Em atendimento")
        self.waiting_list=QListWidget(); self.tabs.addTab(self._list_panel(self.waiting_list),"Aguardando entrega")
        self.sent_list=QListWidget(); self.sent_list.currentItemChanged.connect(self._sent_selected); self.tabs.addTab(self._sent_tab(),"Enviados")
        self.inbox_list=QListWidget(); self.inbox_list.currentItemChanged.connect(self._inbox_selected); self.tabs.addTab(self._inbox_tab(),"Documentos recebidos")
        self.basket_panel=self._basket_tab(); self.tabs.addTab(self.basket_panel,"Cesta de documentos")
        self.history_list=QListWidget(); self.tabs.addTab(self._list_panel(self.history_list),"Histórico")
        self.status=QLabel("Pronto"); root.addWidget(self.status)
    def _requests_tab(self):
        panel=QWidget(); layout=QHBoxLayout(panel); self.requests_list=QListWidget(); layout.addWidget(self.requests_list,2)
        form=QFormLayout(); self.request_title=QLineEdit(); self.request_description=QTextEdit(); self.request_description.setMaximumHeight(80); self.assignee=QComboBox(); self.assignee.addItem("Sem responsável",None); self.due=QLineEdit(); self.due.setPlaceholderText("AAAA-MM-DDTHH:MM (opcional)")
        form.addRow("Documento solicitado",self.request_title); form.addRow("Descrição",self.request_description); form.addRow("Responsável",self.assignee); form.addRow("Prazo",self.due)
        self.create_request_button=QPushButton("Criar solicitação"); self.create_request_button.clicked.connect(lambda:self.create_request_requested.emit({"title":self.request_title.text(),"description":self.request_description.toPlainText(),"assigned_to_user_id":self.assignee.currentData(),"due_at":self.due.text().strip() or None})); form.addRow(self.create_request_button)
        self.request_status=QComboBox()
        for code,label in (("IN_PROGRESS","Iniciar atendimento"),("ATTENDED","Marcar atendida"),("CANCELLED","Cancelar")): self.request_status.addItem(label,code)
        self.update_request_button=QPushButton("Atualizar estado"); self.update_request_button.clicked.connect(self._request_update); form.addRow(self.request_status,self.update_request_button)
        self.prepare_request_button=QPushButton("Preparar entrega da solicitação"); self.prepare_request_button.clicked.connect(lambda:self._emit_id(self.requests_list,self.prepare_request_requested)); form.addRow(self.prepare_request_button)
        layout.addLayout(form,1); return panel
    def _basket_tab(self):
        panel=QWidget(); layout=QVBoxLayout(panel); self.basket_list=QListWidget(); layout.addWidget(self.basket_list)
        self.basket_summary=QLabel("0 documento(s) · 0 B"); layout.addWidget(self.basket_summary)
        row=QHBoxLayout(); self.select_documents_button=QPushButton("Selecionar documentos"); IconProvider.apply(self.select_documents_button,"documents"); self.select_documents_button.clicked.connect(self.select_documents_requested.emit); remove=QPushButton("Remover item"); remove.clicked.connect(self._remove_basket); clear=QPushButton("Limpar cesta"); clear.clicked.connect(self.clear_basket_requested.emit); row.addWidget(self.select_documents_button); row.addWidget(remove); row.addWidget(clear); layout.addLayout(row)
        form=QFormLayout(); self.recipient=QComboBox(); self.peer=QComboBox(); self.message=QLineEdit(); form.addRow("Destinatário",self.recipient); form.addRow("Instalação",self.peer); form.addRow("Mensagem",self.message); layout.addLayout(form)
        self.send_button=QPushButton("Enviar e gerar protocolo"); self.send_button.setObjectName("deliveryPrimary"); IconProvider.apply(self.send_button,"import"); self.send_button.clicked.connect(lambda:self.send_requested.emit({"recipient_user_id":self.recipient.currentData(),"recipient_instance_id":self.peer.currentData(),"message":self.message.text()})); layout.addWidget(self.send_button); return panel
    def _sent_tab(self):
        panel=self._list_panel(self.sent_list); row=QHBoxLayout(); self.retry=QPushButton("Tentar novamente"); self.retry.clicked.connect(lambda:self._emit_id(self.sent_list,self.retry_requested)); self.sent_receipt=QPushButton("Ver comprovante"); self.sent_receipt.clicked.connect(lambda:self._emit_id(self.sent_list,self.receipt_requested)); self.sent_receipt.setEnabled(False); row.addWidget(self.retry); row.addWidget(self.sent_receipt); row.addStretch(); panel.layout().addLayout(row); return panel
    def _inbox_tab(self):
        panel=self._list_panel(self.inbox_list); row=QHBoxLayout()
        for text,signal in (("Visualizar",self.view_requested),("Download",self.download_requested),("Adicionar ao SmartFile",self.add_to_ged_requested)):
            button=QPushButton(text); button.clicked.connect(lambda _checked=False,s=signal:self._emit_id(self.inbox_list,s)); row.addWidget(button)
        self.confirm_receipt=QPushButton("Confirmar recebimento"); self.confirm_receipt.setObjectName("deliveryPrimary"); self.confirm_receipt.clicked.connect(lambda:self._emit_id(self.inbox_list,self.acknowledge_requested)); row.addWidget(self.confirm_receipt)
        self.inbox_receipt=QPushButton("Ver comprovante"); self.inbox_receipt.clicked.connect(lambda:self._emit_id(self.inbox_list,self.receipt_requested)); self.inbox_receipt.setEnabled(False); row.addWidget(self.inbox_receipt)
        panel.layout().addLayout(row); return panel
    @staticmethod
    def _list_panel(widget): panel=QWidget(); layout=QVBoxLayout(panel); layout.addWidget(widget); return panel
    def set_members(self,members):
        self.assignee.clear(); self.assignee.addItem("Sem responsável",None); self.recipient.clear()
        for user in members: self.assignee.addItem(user.display_name,user.id); self.recipient.addItem(user.display_name,user.id)
    def set_peers(self,peers):
        self.peer.clear()
        for peer in peers: self.peer.addItem(f"{peer.device_name} · {peer.current_ip}:{peer.http_port}",peer.instance_id)
    def select_delivery_target(self, user_id, instance_id):
        user_index=self.recipient.findData(user_id); peer_index=self.peer.findData(instance_id)
        if user_index>=0:self.recipient.setCurrentIndex(user_index)
        if peer_index>=0:self.peer.setCurrentIndex(peer_index)
        self.tabs.setCurrentWidget(self.basket_panel)
    def set_requests(self,requests,current_user_id):
        targets=(self.requests_list,self.created_list,self.attending_list,self.waiting_list)
        for widget in targets: widget.clear()
        self.overview_list.clear()
        for request in requests:
            text=f"{request.status} · {request.title}"+(" · ATRASADA" if request.status=="OVERDUE" else ""); item=self._item(text,request.id,request.status); self.requests_list.addItem(item)
            if request.requested_by_user_id==current_user_id:self.created_list.addItem(self._item(text,request.id,request.status))
            if request.status in {"IN_PROGRESS"}:self.attending_list.addItem(self._item(text,request.id,request.status))
            if request.status in {"ATTENDED","DELIVERING"}:self.waiting_list.addItem(self._item(text,request.id,request.status))
            if request.assigned_to_user_id==current_user_id and request.status not in {"COMPLETED","CANCELLED"}:self.overview_list.addItem(f"Solicitação · {text}")
    def set_basket(self,basket):
        self.basket_list.clear()
        for item in basket.items:self.basket_list.addItem(self._item(f"{item.logical_name} · {item.size/1024:.1f} KB",item.document_id,""))
        self.basket_summary.setText(f"{len(basket.items)} documento(s) · {basket.total_size/1024:.1f} KB")
    def set_deliveries(self,outgoing,incoming,receipt_delivery_ids=()):
        receipt_delivery_ids=set(receipt_delivery_ids)
        self.sent_list.clear(); self.inbox_list.clear()
        for delivery in outgoing:
            item=self._item(f"{delivery.protocol_number} · {delivery.status}",delivery.id,delivery.status);item.setData(Qt.ItemDataRole.UserRole+2,delivery.id in receipt_delivery_ids);self.sent_list.addItem(item)
        for delivery in incoming:
            item=self._item(f"{delivery.protocol_number} · {delivery.status}",delivery.id,delivery.status);item.setData(Qt.ItemDataRole.UserRole+2,delivery.id in receipt_delivery_ids);self.inbox_list.addItem(item)
            if delivery.status in {"DELIVERED","VIEWED"}:self.overview_list.addItem(f"Documento recebido · {delivery.protocol_number} · {delivery.status}")
    def set_history(self,events):
        self.history_list.clear()
        for event in events:self.history_list.addItem(f"{event.created_at[:16].replace('T',' ')} · {event.description}")
    def show_status(self,message):self.status.setText(message)
    def set_permissions(self,context):
        can_request=context.has_permission("document.request.create");can_update=context.has_permission("document.request.update");can_send=context.has_permission("delivery.create") and context.has_permission("delivery.send")
        self._can_acknowledge=context.has_permission("delivery.acknowledge");self.create_request_button.setEnabled(can_request);self.update_request_button.setEnabled(can_update);self.request_status.setEnabled(can_update);self.prepare_request_button.setEnabled(can_update and can_send);self.select_documents_button.setEnabled(can_send);self.send_button.setEnabled(can_send);self.configure.setVisible(context.has_permission("delivery.configure"))
    def _request_update(self):self._emit_id(self.requests_list,lambda value:self.request_status_requested.emit(value,str(self.request_status.currentData())))
    def _remove_basket(self):self._emit_id(self.basket_list,self.remove_basket_requested)
    @staticmethod
    def _item(text,id_value,status): item=QListWidgetItem(text); item.setData(Qt.ItemDataRole.UserRole,id_value); item.setData(Qt.ItemDataRole.UserRole+1,status); return item
    @staticmethod
    def _emit_id(widget,signal):
        item=widget.currentItem()
        if item:signal.emit(int(item.data(Qt.ItemDataRole.UserRole))) if hasattr(signal,"emit") else signal(int(item.data(Qt.ItemDataRole.UserRole)))
    def select_tab(self,key):
        targets={"received":self.inbox_list,"sent":self.sent_list,"history":self.history_list}
        widget=targets.get(key)
        if widget is not None:self.tabs.setCurrentWidget(widget.parentWidget())
    def _sent_selected(self,item,*_):
        self.sent_receipt.setEnabled(bool(item and item.data(Qt.ItemDataRole.UserRole+2)))
    def _inbox_selected(self,item,*_):
        status=str(item.data(Qt.ItemDataRole.UserRole+1)) if item else "";has_receipt=bool(item and item.data(Qt.ItemDataRole.UserRole+2))
        self.confirm_receipt.setEnabled(bool(item and self._can_acknowledge and status in {"DELIVERED","VIEWED"} and not has_receipt));self.inbox_receipt.setEnabled(has_receipt)
