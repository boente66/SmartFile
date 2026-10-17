from PyQt6.QtWidgets import QComboBox, QCheckBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox, QWidget


class SignatureQrOptions(QWidget):
    def __init__(self, page_count, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        self.visible = QCheckBox("Adicionar QR de validação")
        self.position = QComboBox()
        self.position.addItem("Abaixo da assinatura", "below")
        self.position.addItem("Ao lado da assinatura", "right")
        self.position.addItem("Posição manual", "manual")
        self._anchor = None
        self._updating = False
        self._placement_error = None
        self.mode = QLabel("Modo local — funciona sem URL pública")
        self.page = QSpinBox(); self.page.setRange(1, max(1, page_count))
        self.x = QDoubleSpinBox(); self.y = QDoubleSpinBox(); self.size = QDoubleSpinBox()
        for spin in (self.x, self.y, self.size):
            spin.setRange(0, 5000)
        self.x.setValue(20); self.y.setValue(20)
        self.size.setRange(60, 300); self.size.setValue(90)
        layout.addRow(self.visible); layout.addRow(self.mode)
        layout.addRow("Posição:", self.position)
        layout.addRow("Página do QR:", self.page)
        layout.addRow("X (pontos):", self.x); layout.addRow("Y (pontos):", self.y)
        layout.addRow("Tamanho (pontos):", self.size)
        hint = QLabel("O QR identifica o original registrado. Compare o arquivo recebido para verificar sua integridade. Uma marca manuscrita continua sendo visual.")
        hint.setWordWrap(True); layout.addRow(hint)
        self.visible.toggled.connect(self._enable); self._enable(False)
        self.position.currentIndexChanged.connect(self._place_adjacent)
        self.size.valueChanged.connect(self._place_adjacent)
        for field in (self.x, self.y):
            field.valueChanged.connect(self._manual)

    def set_anchor(self, page_size, rectangle, page_number, caption=0):
        self._anchor = (page_size, rectangle, page_number, caption)
        self._place_adjacent()

    def _manual(self):
        if not self._updating:
            self._placement_error = None
            self.position.setCurrentIndex(2)

    def _place_adjacent(self):
        self._placement_error = None
        if not self._anchor or self.position.currentData() == "manual":
            return
        from app.utils.qr_placement import adjacent_qr
        page_size, rect, page_number, caption = self._anchor
        try:
            qr = adjacent_qr(page_size, rect, self.size.value(), self.position.currentData(), caption)
        except ValueError as exc:
            self._placement_error = str(exc)
            self.mode.setText(str(exc))
            return
        self._updating = True
        try:
            self.x.setValue(qr[0]); self.y.setValue(qr[1]); self.page.setValue(page_number)
        finally:
            self._updating = False

    def set_base_url(self, base_url):
        self.mode.setText("Modo web configurado — publicação não automática" if base_url else "Modo local — funciona sem URL pública")

    def _enable(self, enabled):
        for field in (self.position, self.page, self.x, self.y, self.size):
            field.setEnabled(enabled)

    def values(self):
        if self.visible.isChecked() and self._placement_error:
            raise ValueError(self._placement_error)
        size = self.size.value(); x, y = self.x.value(), self.y.value()
        return dict(qr_visible=self.visible.isChecked(), qr_page_number=self.page.value(),
                    qr_rect=(x, y, x + size, y + size))
