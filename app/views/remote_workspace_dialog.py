from PyQt6.QtCore import Qt,pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,QHBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton,QVBoxLayout,
)
from app.ui.icon_provider import IconProvider


class RemoteWorkspaceDialog(QDialog):
    add_requested=pyqtSignal();scan_requested=pyqtSignal(int);unmount_requested=pyqtSignal(int)
    reconcile_requested=pyqtSignal(str)
    def __init__(self,mounts,parent=None):
        super().__init__(parent);self.setWindowTitle("Acervo remoto multicloud");self.resize(700,480)
        layout=QVBoxLayout(self);layout.addWidget(QLabel(
            "Espelhos lógicos de pastas existentes. Atualizar é somente leitura; "
            "desmontar remove apenas o catálogo local."
        ))
        self.list=QListWidget();layout.addWidget(self.list,1)
        for mount in mounts:
            item=QListWidgetItem(
                f"{mount.logical_mount_name}  ·  {mount.provider}  ·  {mount.status}"
            );item.setData(Qt.ItemDataRole.UserRole,mount);self.list.addItem(item)
        row=QHBoxLayout();self.add=QPushButton("Montar pasta");IconProvider.apply(self.add,"cloud_add")
        self.scan=QPushButton("Atualizar espelho");IconProvider.apply(self.scan,"cloud_sync")
        self.reconcile=QPushButton("Comparar e planejar");IconProvider.apply(self.reconcile,"cloud_sync")
        self.unmount=QPushButton("Desmontar");IconProvider.apply(self.unmount,"action_trash")
        self.close=QPushButton("Fechar")
        for button in (self.add,self.scan,self.reconcile,self.unmount):row.addWidget(button)
        row.addStretch();row.addWidget(self.close);layout.addLayout(row)
        self.add.clicked.connect(self.add_requested);self.scan.clicked.connect(self._scan)
        self.reconcile.clicked.connect(self._reconcile);self.unmount.clicked.connect(self._unmount)
        self.close.clicked.connect(self.accept)
    def selected(self):
        item=self.list.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else None
    def _scan(self):
        value=self.selected()
        if value:self.scan_requested.emit(value.id)
    def _reconcile(self):
        value=self.selected()
        if value:self.reconcile_requested.emit(value.collection_key)
    def _unmount(self):
        value=self.selected()
        if value:self.unmount_requested.emit(value.id)
