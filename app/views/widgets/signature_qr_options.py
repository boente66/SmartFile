from PyQt6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox, QWidget


class SignatureQrOptions(QWidget):
    def __init__(self, page_count, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.visible = QCheckBox("Adicionar QR de validação")
        self.mode = QLabel("Modo local — funciona sem URL pública")
        self.page = QSpinBox(); self.page.setRange(1, max(1, page_count))
        self.x = QDoubleSpinBox(); self.y = QDoubleSpinBox(); self.size = QDoubleSpinBox()
        for spin in (self.x, self.y, self.size):
            spin.setRange(0, 5000)
        self.x.setValue(20); self.y.setValue(20)
        self.size.setRange(60, 300); self.size.setValue(90)
        layout.addRow(self.visible); layout.addRow(self.mode)
        layout.addRow("Página do QR:", self.page)
        layout.addRow("X (pontos):", self.x); layout.addRow("Y (pontos):", self.y)
        layout.addRow("Tamanho (pontos):", self.size)
        hint = QLabel("O QR identifica o original registrado. Compare o arquivo recebido para verificar sua integridade. Uma marca manuscrita continua sendo visual.")
        hint.setWordWrap(True); layout.addRow(hint)
        self.visible.toggled.connect(self._enable); self._enable(False)

    def set_base_url(self, base_url):
        self.mode.setText("Modo web configurado — publicação não automática" if base_url else "Modo local — funciona sem URL pública")

    def _enable(self, enabled):
        for field in (self.page, self.x, self.y, self.size):
            field.setEnabled(enabled)

    def values(self):
        size = self.size.value(); x, y = self.x.value(), self.y.value()
        return dict(qr_visible=self.visible.isChecked(), qr_page_number=self.page.value(),
                    qr_rect=(x, y, x + size, y + size))
