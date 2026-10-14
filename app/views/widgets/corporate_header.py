import base64

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QPushButton, QMessageBox

from app.models.corporate_identity import CorporateIdentity


class CorporateHeader(QFrame):
    """Componente fixo: dados institucionais nunca definem layout ou estilos arbitrários."""
    def __init__(self, parent=None, *, show_image=False):
        super().__init__(parent)
        self.setObjectName('corporateIdentityHeader')
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 7, 12, 7)
        self.logo = QLabel()
        self.logo.setFixedSize(40,40)
        root.addWidget(self.logo)
        labels = QVBoxLayout()
        self.name, self.unit, self.product = QLabel(), QLabel(), QLabel('SmartFile')
        for label in (self.name,self.unit,self.product):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            labels.addWidget(label)
        root.addLayout(labels,1)
        self.information=QPushButton('Informações institucionais')
        self.information.clicked.connect(self.show_information)
        root.addWidget(self.information)
        self._identity=None
        self.image = QLabel()
        self.image.setFixedSize(120,65)
        self.image.setVisible(show_image)
        self._show_image = show_image
        root.addWidget(self.image)
        self.hide()

    def apply_identity(self, identity, fallback='SmartFile'):
        self._identity=identity
        foreground = CorporateIdentity.foreground(identity.header_color)
        accent_foreground = CorporateIdentity.foreground(identity.accent_color)
        self.setStyleSheet(f'QFrame#corporateIdentityHeader {{background:{identity.header_color}; border:2px solid {identity.accent_color}; border-radius:6px;}}')
        for label in (self.name,self.unit,self.product,self.logo,self.image):
            label.setStyleSheet(f'color:{foreground}; background:transparent; border:none;')
        self.information.setStyleSheet(f'color:{foreground}; background:transparent; border:1px solid {foreground}; padding:4px;')
        self.information.setVisible(bool(identity.legal_name or identity.cnpj or identity.address or identity.privacy_notice or identity.privacy_contact))
        self.name.setText(identity.title(fallback))
        self.name.setAccessibleName('Nome institucional: ' + identity.title(fallback))
        self.unit.setText(identity.unit)
        self.unit.setVisible(bool(identity.unit))
        self.product.setText('SmartFile')
        for key, label, bounds in (('logo',self.logo,(40,40)),('institutional_image',self.image,(120,65))):
            label.clear()
            encoded = getattr(identity,key)
            label.setVisible(bool(encoded) and (key=='logo' or self._show_image))
            if encoded:
                pixmap = QPixmap()
                pixmap.loadFromData(base64.b64decode(encoded))
                label.setPixmap(pixmap.scaled(*bounds,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                label.setAccessibleName('Logo institucional' if key=='logo' else 'Imagem institucional')
        self.setVisible(bool(identity.authority_instance_id or identity.display_name or identity.logo or identity.legal_name))

    def show_information(self):
        identity=self._identity
        if identity is None:return
        lines=['SmartFile — informações declaradas pela organização',identity.title()]
        for label,key in (('Razão social','legal_name'),('CNPJ','cnpj'),('Endereço','address'),('Setor/unidade','unit'),('Canal de privacidade','privacy_contact')):
            if getattr(identity,key):lines.append(label+': '+getattr(identity,key))
        if identity.privacy_notice:lines+=['','Aviso institucional de privacidade',identity.privacy_notice]
        message=QMessageBox(self)
        message.setWindowTitle('SmartFile — organização e privacidade')
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText('\n'.join(lines))
        message.exec()
