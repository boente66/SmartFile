from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QSpinBox,
    QVBoxLayout,
)


class DeliveryNetworkDialog(QDialog):
    """Configuração explícita da identidade local e dos peers autorizados."""

    save_local_requested = pyqtSignal(dict)
    save_peer_requested = pyqtSignal(dict)
    remove_peer_requested = pyqtSignal(str)

    def __init__(self, local, peers, members, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar entrega SmartFile na LAN")
        self.resize(760, 590)
        root = QVBoxLayout(self)
        note = QLabel(
            "O UUID identifica esta instalação. O IP e a porta apenas indicam "
            "onde ela está disponível na rede local confiável."
        )
        note.setWordWrap(True); root.addWidget(note)

        local_box = QGroupBox("Esta instalação")
        local_form = QFormLayout(local_box)
        identity = QLineEdit(local.instance_id); identity.setReadOnly(True)
        self.local_name = QLineEdit(local.device_name)
        self.local_host = QLineEdit(local.current_ip)
        self.local_port = QSpinBox(); self.local_port.setRange(1024, 65535); self.local_port.setValue(local.http_port)
        local_form.addRow("SmartFile ID", identity); local_form.addRow("Nome", self.local_name)
        local_form.addRow("IP/endereço atual", self.local_host); local_form.addRow("Porta", self.local_port)
        save_local = QPushButton("Salvar configuração local")
        save_local.clicked.connect(lambda: self.save_local_requested.emit(self.local_values()))
        local_form.addRow(save_local); root.addWidget(local_box)

        peers_box = QGroupBox("Instalações autorizadas")
        peers_layout = QHBoxLayout(peers_box)
        self.peers = QListWidget(); peers_layout.addWidget(self.peers, 1)
        form = QFormLayout(); self.peer_id = QLineEdit(); self.peer_name = QLineEdit()
        self.peer_host = QLineEdit(); self.peer_port = QSpinBox(); self.peer_port.setRange(1024, 65535); self.peer_port.setValue(8765)
        self.peer_owner = QComboBox()
        for member in members: self.peer_owner.addItem(member.display_name, member.id)
        form.addRow("SmartFile ID", self.peer_id); form.addRow("Nome", self.peer_name)
        form.addRow("IP/endereço", self.peer_host); form.addRow("Porta", self.peer_port)
        form.addRow("Usuário desta instalação", self.peer_owner)
        save_peer = QPushButton("Adicionar ou atualizar peer")
        remove_peer = QPushButton("Remover peer selecionado")
        save_peer.clicked.connect(lambda: self.save_peer_requested.emit(self.peer_values()))
        remove_peer.clicked.connect(self._remove_selected)
        form.addRow(save_peer); form.addRow(remove_peer); peers_layout.addLayout(form, 2)
        root.addWidget(peers_box, 1)
        self.set_peers(peers)
        self.peers.currentItemChanged.connect(self._select_peer)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept); root.addWidget(buttons)

    def local_values(self):
        return {"device_name": self.local_name.text(), "host": self.local_host.text(), "port": self.local_port.value()}

    def peer_values(self):
        return {"instance_id": self.peer_id.text(), "device_name": self.peer_name.text(), "host": self.peer_host.text(), "port": self.peer_port.value(), "owner_user_id": self.peer_owner.currentData()}

    def set_peers(self, peers):
        selected = self.peer_id.text().strip()
        self.peers.clear()
        for peer in peers:
            item = QListWidgetItem(f"{peer.device_name} · {peer.current_ip}:{peer.http_port}")
            item.setData(Qt.ItemDataRole.UserRole, peer)
            self.peers.addItem(item)
            if peer.instance_id == selected:self.peers.setCurrentItem(item)

    def _select_peer(self, current, _previous):
        if current is None:return
        peer=current.data(Qt.ItemDataRole.UserRole);self.peer_id.setText(peer.instance_id);self.peer_name.setText(peer.device_name);self.peer_host.setText(peer.current_ip);self.peer_port.setValue(peer.http_port)
        index=self.peer_owner.findData(peer.owner_user_id)
        if index>=0:self.peer_owner.setCurrentIndex(index)

    def _remove_selected(self):
        item=self.peers.currentItem()
        if item:self.remove_peer_requested.emit(item.data(Qt.ItemDataRole.UserRole).instance_id)
