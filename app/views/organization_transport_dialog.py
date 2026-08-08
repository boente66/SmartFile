from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QLineEdit, QVBoxLayout,
)


class OrganizationTransportDialog(QDialog):
    test_requested = pyqtSignal(dict)

    def __init__(self, settings, summary: dict | None = None, parent=None):
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
        summary = summary or {}
        self.transport_status = QLabel(self._summary_text(summary))
        self.transport_status.setWordWrap(True)
        root.addWidget(self.transport_status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        self.test_button = buttons.addButton(
            "Testar conexão", QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.test_button.clicked.connect(lambda: self.test_requested.emit(self.values()))
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.mode.currentIndexChanged.connect(self._update_state); self._update_state()
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
        self.test_button.setEnabled(remote)

    def set_test_busy(self, busy: bool) -> None:
        self.test_button.setEnabled(not busy and self.mode.currentData() != "LOCAL")
        self.save_button.setEnabled(not busy)
        if busy:
            self.transport_status.setText("Testando conexão...")

    def show_test_result(self, success: bool, message: str) -> None:
        prefix = "Conectado" if success else "Falha"
        self.transport_status.setText(f"{prefix}: {message}")

    @staticmethod
    def _summary_text(summary: dict) -> str:
        enabled = "Ativo" if summary.get("enabled") else "Inativo"
        mode = summary.get("mode", "LOCAL")
        last = summary.get("last_test_message") or "ainda não testado"
        tested_at = str(summary.get("last_test_at") or "").replace("T", " ")[:16]
        if tested_at:
            last = f"{tested_at} — {last}"
        return (
            f"Transporte {mode}: {enabled} · Último teste: {last} · "
            f"Jobs pendentes: {summary.get('pending', 0)} · "
            f"Falhas: {summary.get('failed', 0)}"
        )
