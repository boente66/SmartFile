from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QVBoxLayout,
)


class OrganizationTransportDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Camada de transporte empresarial")
        self.resize(560, 300)
        root = QVBoxLayout(self)
        note = QLabel(
            "Configura o destino administrado pela TI. Credenciais não são aceitas no endereço "
            "e a ativação não substitui o storage interno do SmartFile."
        )
        note.setWordWrap(True); root.addWidget(note)
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem("Somente local", "LOCAL")
        self.mode.addItem("NAS / compartilhamento", "NAS")
        self.mode.addItem("Servidor HTTPS", "HTTPS")
        self.mode.addItem("Servidor LAN", "LAN")
        index = self.mode.findData(settings.mode); self.mode.setCurrentIndex(max(index, 0))
        self.endpoint = QLineEdit(settings.endpoint or "")
        self.endpoint.setPlaceholderText("/mnt/nas/smartfile, https://ged.exemplo ou servidor/pasta")
        self.enabled = QCheckBox("Ativar transporte após salvar"); self.enabled.setChecked(settings.enabled)
        self.verify_tls = QCheckBox("Validar certificado TLS"); self.verify_tls.setChecked(settings.verify_tls)
        form.addRow("Modo:", self.mode); form.addRow("Destino:", self.endpoint)
        form.addRow("", self.enabled); form.addRow("", self.verify_tls)
        root.addLayout(form)
        self.mode.currentIndexChanged.connect(self._update_state); self._update_state()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)

    def values(self) -> dict:
        return {
            "mode": str(self.mode.currentData()), "endpoint": self.endpoint.text(),
            "enabled": self.enabled.isChecked(), "verify_tls": self.verify_tls.isChecked(),
        }

    def _update_state(self) -> None:
        remote = self.mode.currentData() != "LOCAL"
        self.endpoint.setEnabled(remote); self.enabled.setEnabled(remote)
        self.verify_tls.setVisible(self.mode.currentData() == "HTTPS")
