from dataclasses import asdict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QColorDialog, QFileDialog,
    QScrollArea, QWidget, QCheckBox, QComboBox)

from app.models.corporate_identity import CorporateIdentity
from app.views.widgets.corporate_header import CorporateHeader
from app.views.widgets.dialog_theme import apply_import_theme


class CorporateDesignDialog(QDialog):
    save_requested = pyqtSignal(dict, object)
    preview_requested = pyqtSignal(dict)
    image_requested = pyqtSignal(str, str)

    def __init__(self, identity, peers=(), source=None, parent=None):
        super().__init__(parent)
        apply_import_theme(self)
        self.setWindowTitle('SmartFile — Modo Design Corporativo')
        self.resize(900,650)
        self._images = {'logo':identity.logo,'institutional_image':identity.institutional_image}
        self._local_controls = []
        root = QHBoxLayout(self)
        scroll = QScrollArea();scroll.setWidgetResizable(True)
        form_widget=QWidget();form=QFormLayout(form_widget);scroll.setWidget(form_widget)
        root.addWidget(scroll,3)
        preview=QVBoxLayout();root.addLayout(preview,2)
        self.source=QComboBox();self.source.addItem('Esta instalação — editar aqui',None)
        for peer in peers:self.source.addItem(f'{peer.device_name} — {peer.instance_id}',peer.instance_id)
        self.source.setCurrentIndex(max(0,self.source.findData(source['instance_id'] if source else None)))
        form.addRow('Fonte compartilhada:',self.source)
        self.edits={}
        labels={'display_name':'Nome de exibição','unit':'Setor/unidade','legal_name':'Razão social',
            'cnpj':'CNPJ (numérico ou alfanumérico)','address':'Endereço institucional','privacy_contact':'Canal de privacidade',
            'accent_color':'Cor de destaque','header_color':'Cor do cabeçalho'}
        for key,label in labels.items():
            edit=QLineEdit(getattr(identity,key));self.edits[key]=edit
            edit.setMaxLength(500 if key=='address' else 180)
            if key.endswith('_color'):
                row=QHBoxLayout();row.addWidget(edit)
                choose=QPushButton('Escolher');self._local_controls.append(choose);choose.clicked.connect(lambda _,k=key:self.choose_color(k));row.addWidget(choose)
                form.addRow(label,row)
            else:form.addRow(label,edit)
        for key,label in (('logo','Logo'),('institutional_image','Imagem institucional opcional')):
            row=QHBoxLayout();choose=QPushButton('Escolher arquivo');clear=QPushButton('Remover')
            self._local_controls.extend((choose, clear))
            choose.clicked.connect(lambda _,k=key:self.choose_image(k));clear.clicked.connect(lambda _,k=key:self.set_image(k,''))
            row.addWidget(choose);row.addWidget(clear);form.addRow(label,row)
        self.notice=QTextEdit();self.notice.setPlainText(identity.privacy_notice);self.notice.setMaximumHeight(110)
        form.addRow('Aviso de privacidade institucional:',self.notice)
        self.legal=QCheckBox('Incluir razão social, CNPJ e endereço nos comprovantes')
        self.legal.setChecked(identity.show_legal_details_on_receipts);form.addRow(self.legal)
        hint=QLabel('Dados declarados pela organização. A validação do CNPJ não comprova titularidade. A organização define finalidade, base legal e retenção; evite dados pessoais desnecessários.')
        hint.setWordWrap(True);form.addRow(hint)
        self.preview=CorporateHeader(show_image=True);preview.addWidget(QLabel('Prévia'));preview.addWidget(self.preview)
        self.error=QLabel();self.error.setObjectName("errorLabel");self.error.setWordWrap(True);preview.addWidget(self.error);preview.addStretch()
        show=QPushButton('Atualizar prévia');show.clicked.connect(lambda:self.preview_requested.emit(self.values()));preview.addWidget(show)
        reset=QPushButton('Restaurar padrão SmartFile');self._local_controls.append(reset);reset.clicked.connect(self.restore_visual);preview.addWidget(reset)
        save=QPushButton('Salvar');save.clicked.connect(lambda:self.save_requested.emit(self.values(),self.source.currentData()));preview.addWidget(save)
        close=QPushButton('Fechar');close.clicked.connect(self.reject);preview.addWidget(close)
        self.preview.apply_identity(identity)
        self.source.currentIndexChanged.connect(self._source_changed)
        self._source_changed()

    def _source_changed(self):
        remote=bool(self.source.currentData())
        for edit in self.edits.values():edit.setReadOnly(remote)
        self.notice.setReadOnly(remote);self.legal.setEnabled(not remote)
        for control in self._local_controls:control.setEnabled(not remote)

    def values(self):
        values={key:edit.text() for key,edit in self.edits.items()}
        values.update(self._images)
        values['privacy_notice']=self.notice.toPlainText()
        values['show_legal_details_on_receipts']=self.legal.isChecked()
        return values

    def load_identity(self,identity):
        for key,edit in self.edits.items():edit.setText(getattr(identity,key))
        self.notice.setPlainText(identity.privacy_notice)
        self.legal.setChecked(identity.show_legal_details_on_receipts)
        self._images={'logo':identity.logo,'institutional_image':identity.institutional_image}
        self.preview.apply_identity(identity)

    def choose_color(self,key):
        if self.source.currentData():return
        color=QColorDialog.getColor(QColor(self.edits[key].text()),self,'Cor institucional')
        if color.isValid():self.edits[key].setText(color.name())

    def choose_image(self,key):
        if self.source.currentData():return
        path,_=QFileDialog.getOpenFileName(self,'Imagem institucional','','Imagens (*.png *.jpg *.jpeg *.webp)')
        if path:self.image_requested.emit(key,path)

    def set_image(self,key,encoded):
        if self.source.currentData():return
        self._images[key]=encoded
        self.preview_requested.emit(self.values())

    def restore_visual(self):
        if self.source.currentData():return
        defaults=CorporateIdentity()
        for key in ('display_name','unit','accent_color','header_color'):self.edits[key].setText(getattr(defaults,key))
        self._images={'logo':'','institutional_image':''}
        self.preview_requested.emit(self.values())
