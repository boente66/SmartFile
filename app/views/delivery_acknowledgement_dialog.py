from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QMessageBox, QVBoxLayout,
)

from app.views.widgets.signature_acquisition_widget import SignatureAcquisitionWidget


class DeliveryAcknowledgementDialog(QDialog):
    def __init__(self, protocol, sender_name, items, parent=None):
        super().__init__(parent)
        self.setObjectName("deliveryAcknowledgementDialog")
        self.setWindowTitle("Confirmar recebimento")
        self.resize(760, 650)
        self.setMinimumSize(640, 560)
        root = QVBoxLayout(self)
        title = QLabel("Confirmar recebimento")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        summary = QLabel(
            f"<b>Protocolo</b><br>{protocol}<br><br>"
            f"<b>Recebido de</b><br>{sender_name or '—'}"
        )
        root.addWidget(summary)
        root.addWidget(QLabel("<b>Documentos verificados</b>"))
        documents = QLabel("\n".join(f"✓ {item.logical_name}" for item in items))
        documents.setWordWrap(True)
        root.addWidget(documents)
        declaration = QLabel(
            "Confirmo o recebimento dos documentos relacionados ao protocolo acima."
        )
        declaration.setObjectName("acknowledgementDeclaration")
        declaration.setWordWrap(True)
        root.addWidget(declaration)
        root.addWidget(QLabel("<b>Como deseja assinar?</b>"))
        self.acquisition = SignatureAcquisitionWidget()
        root.addWidget(self.acquisition, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Confirmar recebimento"
        )
        buttons.accepted.connect(self._accept_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def signature(self) -> tuple[bytes, str]:
        return self.acquisition.signature_bytes(), self.acquisition.method

    def clear_signature(self) -> None:
        self.acquisition.clear()

    def _accept_valid(self) -> None:
        if not self.acquisition.signature_bytes():
            QMessageBox.warning(
                self, "Confirmar recebimento",
                "Desenhe ou importe uma assinatura visual antes de confirmar.",
            )
            return
        self.accept()

