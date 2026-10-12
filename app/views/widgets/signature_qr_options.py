from PyQt6.QtWidgets import QCheckBox,QDoubleSpinBox,QFormLayout,QLabel,QLineEdit,QSpinBox,QWidget


class SignatureQrOptions(QWidget):
    def __init__(self,page_count,parent=None):
        super().__init__(parent)
        layout=QFormLayout(self)
        self.visible=QCheckBox("Exibir QR Code no documento")
        self.url=QLineEdit();self.url.setPlaceholderText("https://…/documento-assinado.pdf")
        self.page=QSpinBox();self.page.setRange(1,max(1,page_count))
        self.x=QDoubleSpinBox();self.y=QDoubleSpinBox();self.size=QDoubleSpinBox()
        for spin in (self.x,self.y,self.size):spin.setRange(0,5000)
        self.x.setValue(20);self.y.setValue(20);self.size.setRange(40,300);self.size.setValue(80)
        layout.addRow(self.visible);layout.addRow("Endereço de verificação:",self.url)
        layout.addRow("Página do QR:",self.page);layout.addRow("X (pontos):",self.x);layout.addRow("Y (pontos):",self.y);layout.addRow("Tamanho (pontos):",self.size)
        hint=QLabel("O endereço deve disponibilizar o documento final ou uma página de verificação. O QR não autentica sozinho uma marca manuscrita.")
        hint.setWordWrap(True);layout.addRow(hint)
        self.visible.toggled.connect(self._enable);self._enable(False)

    def _enable(self,enabled):
        for field in (self.url,self.page,self.x,self.y,self.size):field.setEnabled(enabled)

    def values(self):
        size=self.size.value();x,y=self.x.value(),self.y.value()
        return dict(qr_visible=self.visible.isChecked(),verification_url=self.url.text().strip() or None,
                    qr_page_number=self.page.value(),qr_rect=(x,y,x+size,y+size))
