from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,QDialog,QDialogButtonBox,QFormLayout,QLabel,QLineEdit,QProgressBar,
    QTreeWidget,QTreeWidgetItem,QVBoxLayout,
)

from app.cloud.cloud_models import RemoteItemType
from app.ui.icon_provider import IconProvider


class RemoteMountDialog(QDialog):
    browse_requested=pyqtSignal(int,object)
    def __init__(self,accounts,parent=None):
        super().__init__(parent);self.setWindowTitle("Montar acervo remoto");self.resize(660,520)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Selecione uma pasta existente. Montar apenas cataloga metadados: "
            "nenhum arquivo será copiado, importado ou alterado."
        ))
        form=QFormLayout();self.account=QComboBox()
        for value in accounts:self.account.addItem(
            f"{value.provider} — {value.display_name or value.email or 'Conta'}",value
        )
        self.logical_name=QLineEdit();self.logical_name.setPlaceholderText("Ex.: Faculdade")
        self.collection_key=QLineEdit();self.collection_key.setPlaceholderText(
            "Identificador compartilhado opcional para comparar duas montagens"
        )
        form.addRow("Conta",self.account);form.addRow("Nome no SmartFile",self.logical_name)
        form.addRow("Coleção lógica",self.collection_key);layout.addLayout(form)
        self.tree=QTreeWidget();self.tree.setHeaderLabels(["Pasta remota","Provedor"])
        self.tree.itemExpanded.connect(self._expanded);layout.addWidget(self.tree,1)
        self.status=QLabel("Selecione uma conta para carregar a raiz.");layout.addWidget(self.status)
        self.progress=QProgressBar();self.progress.setRange(0,0);self.progress.hide();layout.addWidget(self.progress)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.account.currentIndexChanged.connect(self.load_root)
        if accounts:self.load_root()

    def load_root(self):
        self.tree.clear();account=self.account.currentData()
        if account:self.progress.show();self.browse_requested.emit(account.id,None)

    def populate(self,parent_id,items):
        parent=self._find(parent_id) if parent_id else None
        target=parent or self.tree.invisibleRootItem()
        if parent:
            while parent.childCount():parent.removeChild(parent.child(0))
        for metadata in items:
            if metadata.item_type != RemoteItemType.FOLDER:continue
            item=QTreeWidgetItem([metadata.name,self.account.currentData().provider])
            item.setData(0,Qt.ItemDataRole.UserRole,metadata)
            item.setIcon(0,IconProvider.icon("folder"));item.addChild(QTreeWidgetItem(["Carregando…",""]))
            target.addChild(item)
        self.progress.hide();self.status.setText("Selecione a pasta que deseja montar.")

    def show_error(self,message):self.progress.hide();self.status.setText(message)
    def _expanded(self,item):
        metadata=item.data(0,Qt.ItemDataRole.UserRole)
        if metadata:self.progress.show();self.browse_requested.emit(self.account.currentData().id,metadata.remote_id)
    def _find(self,remote_id):
        iterator=self.tree.findItems("*",Qt.MatchFlag.MatchWildcard|Qt.MatchFlag.MatchRecursive)
        return next((item for item in iterator if getattr(item.data(0,Qt.ItemDataRole.UserRole),"remote_id",None)==remote_id),None)
    def values(self):
        item=self.tree.currentItem();metadata=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        if metadata is None:raise ValueError("Selecione uma pasta remota.")
        account=self.account.currentData();logical=self.logical_name.text().strip() or metadata.name
        return account,metadata,logical,self.collection_key.text().strip() or None
