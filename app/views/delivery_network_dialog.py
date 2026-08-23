from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION


class DeliveryNetworkDialog(QDialog):
    """Configuração visual de descoberta e autorização explícita de peers LAN."""

    save_local_requested = pyqtSignal(dict)
    save_peer_requested = pyqtSignal(dict)
    remove_peer_requested = pyqtSignal(str)
    discover_requested = pyqtSignal()
    authorize_requested = pyqtSignal(object)
    test_peer_requested = pyqtSignal(object)

    def __init__(self, local, peers, members, parent=None):
        super().__init__(parent)
        self.setObjectName("deliveryNetworkDialog")
        self.setWindowTitle("Dispositivos SmartFile")
        self.resize(920, 700)
        self.setMinimumSize(720, 540)
        self.local = local
        self.members = list(members)
        self._peers = list(peers)
        self._discovered = []
        self._connection_states = {}
        self._setup_ui()
        self.set_peers(peers)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 18)
        root.setSpacing(10)
        title = QLabel("Dispositivos SmartFile")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Encontre e autorize instalações SmartFile disponíveis na mesma rede local."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setObjectName("networkDialogScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("networkDialogBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(2, 4, 8, 4)
        body_layout.setSpacing(12)
        local_title = QLabel("Esta instalação")
        local_title.setObjectName("sectionTitle")
        body_layout.addWidget(local_title)
        body_layout.addWidget(self._local_card())

        found_header = QHBoxLayout()
        found_title = QLabel("Dispositivos encontrados")
        found_title.setObjectName("sectionTitle")
        self.discover_button = QPushButton("Procurar SmartFiles")
        IconProvider.apply(self.discover_button, "cloud_sync")
        self.discover_button.clicked.connect(self.discover_requested.emit)
        found_header.addWidget(found_title)
        found_header.addStretch()
        found_header.addWidget(self.discover_button)
        body_layout.addLayout(found_header)
        self.discovery_status = QLabel(
            "Clique em Procurar SmartFiles para iniciar a descoberta local."
        )
        self.discovery_status.setObjectName("networkInfoState")
        self.discovery_status.setWordWrap(True)
        body_layout.addWidget(self.discovery_status)
        self.discovered_container = QVBoxLayout()
        self.discovered_container.setSpacing(8)
        self.discovered_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        body_layout.addLayout(self.discovered_container)

        authorized_title = QLabel("Instalações autorizadas")
        authorized_title.setObjectName("sectionTitle")
        body_layout.addWidget(authorized_title)
        self.authorized_container = QVBoxLayout()
        self.authorized_container.setSpacing(8)
        self.authorized_container.setAlignment(Qt.AlignmentFlag.AlignTop)
        body_layout.addLayout(self.authorized_container)
        body_layout.addWidget(self._manual_section())
        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        footer = QHBoxLayout()
        footer.addStretch()
        footer.addWidget(close_button)
        root.addLayout(footer)

    def _local_card(self) -> QFrame:
        card = self._card()
        card.setProperty("cardRole", "local")
        layout = QVBoxLayout(card)
        heading = QHBoxLayout()
        name = QLabel(self.local.device_name)
        name.setObjectName("deviceName")
        status = QLabel("● Online")
        status.setObjectName("statusOnline")
        heading.addWidget(name)
        heading.addWidget(status)
        heading.addStretch()
        layout.addLayout(heading)
        endpoint = QLabel(
            f"Endereço atual: {self.local.current_ip}:{self.local.http_port}"
        )
        identity = QLabel(f"SmartFile ID: {self.local.instance_id}")
        identity.setObjectName("secondaryText")
        copy_button = QPushButton("Copiar identificação")
        IconProvider.apply(copy_button, "copy")
        copy_button.clicked.connect(
            lambda: QApplication.clipboard().setText(self.local.instance_id)
        )
        row = QHBoxLayout()
        row.addWidget(endpoint)
        row.addStretch()
        row.addWidget(copy_button)
        layout.addLayout(row)
        layout.addWidget(identity)
        group = QGroupBox("Editar esta instalação")
        group.setCheckable(True)
        group.setChecked(False)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self.local_name = QLineEdit(self.local.device_name)
        self.local_host = QLineEdit(self.local.current_ip)
        self.local_port = QSpinBox()
        self.local_port.setRange(1024, 65535)
        self.local_port.setValue(self.local.http_port)
        save = QPushButton("Salvar configuração local")
        save.clicked.connect(
            lambda: self.save_local_requested.emit(self.local_values())
        )
        form.addRow("Nome", self.local_name)
        form.addRow("IP/endereço atual", self.local_host)
        form.addRow("Porta", self.local_port)
        form.addRow(save)
        group_layout = QVBoxLayout(group)
        group_layout.addWidget(form_widget)
        form_widget.setVisible(False)
        group.toggled.connect(form_widget.setVisible)
        layout.addWidget(group)
        return card

    def _manual_section(self) -> QGroupBox:
        group = QGroupBox("Configuração manual")
        group.setCheckable(True)
        group.setChecked(False)
        content = QWidget()
        form = QFormLayout(content)
        self.peer_id = QLineEdit()
        self.peer_name = QLineEdit()
        self.peer_host = QLineEdit()
        self.peer_port = QSpinBox()
        self.peer_port.setRange(1024, 65535)
        self.peer_port.setValue(8765)
        self.peer_owner = QComboBox()
        for member in self.members:
            self.peer_owner.addItem(member.display_name, member.id)
        save = QPushButton("Adicionar ou atualizar peer")
        save.setObjectName("deliveryPrimary")
        save.clicked.connect(self._submit_peer)
        form.addRow("SmartFile ID", self.peer_id)
        form.addRow("Nome", self.peer_name)
        form.addRow("IP/endereço", self.peer_host)
        form.addRow("Porta", self.peer_port)
        form.addRow("Usuário desta instalação", self.peer_owner)
        form.addRow(save)
        layout = QVBoxLayout(group)
        layout.addWidget(content)
        content.setVisible(False)
        group.toggled.connect(content.setVisible)
        self.manual_group = group
        return group

    def local_values(self) -> dict:
        return {
            "device_name": self.local_name.text(),
            "host": self.local_host.text(),
            "port": self.local_port.value(),
        }

    def peer_values(self) -> dict:
        return {
            "instance_id": self.peer_id.text().strip(),
            "device_name": " ".join(self.peer_name.text().split()),
            "host": self.peer_host.text().strip(),
            "port": self.peer_port.value(),
            "owner_user_id": self.peer_owner.currentData(),
        }

    def _submit_peer(self) -> None:
        values = self.peer_values()
        instance_id = values["instance_id"]
        if not instance_id.startswith("SF-") or len(instance_id) <= 3:
            self.show_form_error(
                "SmartFile ID inválido. Use a identificação exibida no outro "
                "SmartFile, iniciada por SF-."
            )
            self.peer_id.setFocus()
            return
        if not values["host"]:
            self.show_form_error("Informe o IP ou endereço da instalação.")
            self.peer_host.setFocus()
            return
        if values["owner_user_id"] is None:
            self.show_form_error(
                "Associe o peer a um membro ativo da organização."
            )
            self.peer_owner.setFocus()
            return
        self.save_peer_requested.emit(values)

    def show_form_error(self, message: str) -> None:
        self.manual_group.setChecked(True)
        self.discovery_status.setObjectName("networkErrorState")
        self.discovery_status.style().unpolish(self.discovery_status)
        self.discovery_status.style().polish(self.discovery_status)
        self.discovery_status.setText(message)

    def set_discovery_state(self, searching: bool, message: str) -> None:
        self.discover_button.setEnabled(not searching)
        self.discover_button.setText(
            "Procurando..." if searching else "Procurar SmartFiles"
        )
        self.discovery_status.setText(message)
        self.discovery_status.setObjectName("networkInfoState")
        self.discovery_status.style().unpolish(self.discovery_status)
        self.discovery_status.style().polish(self.discovery_status)

    def set_discovered(self, devices) -> None:
        self._discovered = list(devices)
        self._clear_layout(self.discovered_container)
        authorized = {peer.instance_id for peer in self._peers}
        visible = [
            device for device in self._discovered
            if device.instance_id != self.local.instance_id
        ]
        if not visible:
            panel = self._card()
            panel.setProperty("cardRole", "empty")
            panel.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
            )
            layout = QVBoxLayout(panel)
            layout.setContentsMargins(18, 14, 18, 14)
            layout.setSpacing(5)
            title = QLabel("Nenhum SmartFile encontrado nesta rede.")
            title.setObjectName("deviceName")
            hint = QLabel(
                "Mantenha o SmartFile aberto nos outros computadores e confirme "
                "que todos estão conectados à mesma rede local."
            )
            hint.setWordWrap(True)
            manual = QPushButton("Configurar manualmente")
            manual.clicked.connect(lambda: self.manual_group.setChecked(True))
            layout.addWidget(title)
            layout.addWidget(hint)
            layout.addWidget(manual, alignment=Qt.AlignmentFlag.AlignLeft)
            self.discovered_container.addWidget(panel)
            return
        for device in visible:
            compatible = device.protocol_version == DELIVERY_PROTOCOL_VERSION
            card = self._device_card(
                device.device_name, device.host, device.port, device.instance_id,
                "● Encontrado" if compatible else "⚠ Incompatível",
                "statusFound" if compatible else "statusError",
            )
            button = QPushButton(
                "Já autorizado" if device.instance_id in authorized else "Autorizar"
            )
            button.setEnabled(compatible and device.instance_id not in authorized)
            button.clicked.connect(
                lambda _checked=False, value=device: self.authorize_requested.emit(value)
            )
            card.layout().itemAt(0).layout().addWidget(button)
            self.discovered_container.addWidget(card)

    def set_peers(self, peers) -> None:
        selected = self.peer_id.text().strip() if hasattr(self, "peer_id") else ""
        self._peers = list(peers)
        self._clear_layout(self.authorized_container)
        if not self._peers:
            label = QLabel(
                "Nenhuma instalação autorizada. Use a descoberta acima ou a "
                "configuração manual."
            )
            label.setObjectName("secondaryText")
            label.setWordWrap(True)
            self.authorized_container.addWidget(label)
        for peer in self._peers:
            state_text, state_object = self._connection_states.get(
                peer.instance_id, ("○ Não verificado", "statusNeutral"),
            )
            card = self._device_card(
                peer.device_name, peer.current_ip, peer.http_port,
                peer.instance_id, state_text, state_object,
            )
            test = QPushButton("Testar conexão")
            test.clicked.connect(
                lambda _checked=False, value=peer: self.test_peer_requested.emit(value)
            )
            edit = QPushButton("Editar")
            edit.clicked.connect(
                lambda _checked=False, value=peer: self._edit_peer(value)
            )
            remove = QPushButton("Remover")
            IconProvider.apply(remove, "trash")
            remove.clicked.connect(
                lambda _checked=False, value=peer:
                self.remove_peer_requested.emit(value.instance_id)
            )
            actions = card.layout().itemAt(0).layout()
            actions.addWidget(test)
            actions.addWidget(edit)
            actions.addWidget(remove)
            self.authorized_container.addWidget(card)
            if peer.instance_id == selected:
                self._edit_peer(peer)
        if hasattr(self, "_discovered"):
            self.set_discovered(self._discovered)

    def show_connection_result(
        self, instance_id: str, success: bool, message: str,
    ) -> None:
        if any(peer.instance_id == instance_id for peer in self._peers):
            self._connection_states[instance_id] = (
                ("● Online", "statusOnline")
                if success else ("○ Offline", "statusError")
            )
            self.set_peers(self._peers)
        self.discovery_status.setObjectName(
            "networkSuccessState" if success else "networkErrorState"
        )
        self.discovery_status.style().unpolish(self.discovery_status)
        self.discovery_status.style().polish(self.discovery_status)
        self.discovery_status.setText(message)

    def show_connection_pending(self, instance_id: str, message: str) -> None:
        self._connection_states[instance_id] = ("⟳ Verificando...", "statusFound")
        self.set_peers(self._peers)
        self.set_discovery_state(False, message)

    def _edit_peer(self, peer) -> None:
        self.manual_group.setChecked(True)
        self.peer_id.setText(peer.instance_id)
        self.peer_name.setText(peer.device_name)
        self.peer_host.setText(peer.current_ip)
        self.peer_port.setValue(peer.http_port)
        index = self.peer_owner.findData(peer.owner_user_id)
        if index >= 0:
            self.peer_owner.setCurrentIndex(index)

    @staticmethod
    def _card() -> QFrame:
        card = QFrame()
        card.setObjectName("networkDeviceCard")
        card.setProperty("networkCard", True)
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        return card

    def _device_card(
        self, name, host, port, instance_id, status, status_object,
    ) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        heading = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setObjectName("deviceName")
        state = QLabel(status)
        state.setObjectName(status_object)
        heading.addWidget(name_label)
        heading.addWidget(state)
        heading.addStretch()
        layout.addLayout(heading)
        layout.addWidget(QLabel(f"Endereço atual: {host}:{port}"))
        identity = QLabel(f"SmartFile ID: {instance_id}")
        identity.setObjectName("secondaryText")
        layout.addWidget(identity)
        return card

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # deleteLater sozinho mantém a geometria anterior visível até o
                # próximo ciclo do event loop e provocava cartões sobrepostos.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
