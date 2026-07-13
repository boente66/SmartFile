from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QVBoxLayout, QWidget,
)

from app.models.registration_request import RegistrationRequest
from app.ui.icon_provider import IconProvider


class FirstUserSetupView(QWidget):
    registration_requested = pyqtSignal(object)
    back_requested = pyqtSignal()

    def __init__(self, first_user: bool = True):
        super().__init__(); self.first_user = first_user; self.setObjectName("authWindow"); self.setWindowTitle("SmartFile — Criar conta")
        self.resize(1200,760); self.setMinimumSize(900,620); self.setWindowIcon(IconProvider.icon("app"))
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._brand_panel(),3); root.addWidget(self._setup_panel(),7)

    def _brand_panel(self):
        panel=QWidget(); panel.setObjectName("authBrandPanel"); layout=QVBoxLayout(panel); layout.setContentsMargins(48,65,48,55)
        logo=QLabel("☁  SmartFile"); logo.setObjectName("authBrandLogo"); layout.addWidget(logo)
        text=QLabel("Seu gerenciamento de documentos\ninteligente e seguro."); text.setObjectName("authBrandSubtitle"); layout.addWidget(text); layout.addStretch()
        for title in ("Seguro","Sincronizado","Produtivo"):
            feature=QLabel(f"✓  {title}\n    Configuração local, organizada e protegida."); feature.setObjectName("authFeature"); feature.setWordWrap(True); layout.addWidget(feature)
        layout.addStretch(); return panel

    def _setup_panel(self):
        outer=QWidget(); outer.setObjectName("authFormBackground"); layout=QVBoxLayout(outer); layout.setContentsMargins(32,25,32,25)
        card=QWidget(); card.setObjectName("authCard"); root=QVBoxLayout(card); root.setContentsMargins(32,25,32,25); root.setSpacing(10)
        title=QLabel("Criar conta"); title.setObjectName("authTitle"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); root.addWidget(title)
        caption_text = ("Configure o primeiro usuário local do SmartFile." if self.first_user else "Crie sua conta local e sua organização independente.")
        caption=QLabel(caption_text); caption.setObjectName("authCaption"); caption.setAlignment(Qt.AlignmentFlag.AlignCenter); root.addWidget(caption)
        fields=QGridLayout(); fields.setHorizontalSpacing(18); fields.setVerticalSpacing(9)
        self.display_name=self._field(fields,0,0,"Nome completo","Digite seu nome completo")
        self.username=self._field(fields,0,1,"Nome de usuário","Escolha um nome de usuário")
        self.email=self._field(fields,2,0,"E-mail (opcional)","seu@email.com")
        self.phone=self._field(fields,2,1,"Telefone (opcional)","(11) 99999-9999")
        self.password=self._field(fields,4,0,"Senha","Crie uma senha",True)
        self.confirmation=self._field(fields,4,1,"Confirmar senha","Confirme sua senha",True)
        root.addLayout(fields)
        hint=QLabel("A senha deve possuir pelo menos 8 caracteres e não pode ser igual ao username."); hint.setObjectName("authHint"); hint.setWordWrap(True); root.addWidget(hint)
        root.addWidget(QLabel("Qual será o uso inicial do SmartFile?"))
        cards=QHBoxLayout(); self.templates=QButtonGroup(self); self.templates.setExclusive(True)
        specs=(("PERSONAL","Pessoal","Uso pessoal"),("STUDENT","Estudante","Estudos"),("BUSINESS","Empresarial","Empresas"),("EMPTY","Começar vazio","Sem pastas"))
        for index,(code,name,description) in enumerate(specs):
            radio=QRadioButton(f"{name}\n{description}"); radio.setObjectName("templateCard"); radio.setProperty("templateCode",code); radio.setMinimumHeight(100); self.templates.addButton(radio); cards.addWidget(radio)
            if index==0: radio.setChecked(True)
        root.addLayout(cards)
        for field in (self.password,self.confirmation):
            toggle=field.addAction(IconProvider.icon("visualize"),QLineEdit.ActionPosition.TrailingPosition); toggle.setToolTip("Mostrar ou ocultar senha"); toggle.triggered.connect(lambda _checked=False,target=field: target.setEchoMode(QLineEdit.EchoMode.Normal if target.echoMode()==QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password))
        self.error_label=QLabel(""); self.error_label.setObjectName("authError"); root.addWidget(self.error_label)
        actions=QHBoxLayout()
        if not self.first_user:
            back=QPushButton("Voltar ao login"); back.setObjectName("authLinkButton"); back.setFlat(True); back.clicked.connect(self.back_requested); actions.addWidget(back)
        actions.addStretch(); submit=QPushButton("Continuar"); submit.setObjectName("authPrimary"); IconProvider.apply(submit,"login"); submit.clicked.connect(self._submit); actions.addWidget(submit); root.addLayout(actions)
        layout.addWidget(card); return outer

    @staticmethod
    def _field(layout,row,column,label,placeholder,password=False):
        layout.addWidget(QLabel(label),row,column); field=QLineEdit(); field.setPlaceholderText(placeholder)
        if password: field.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(field,row+1,column); return field

    def _submit(self):
        selected=self.templates.checkedButton(); code=selected.property("templateCode") if selected else ""
        self.registration_requested.emit(RegistrationRequest(display_name=self.display_name.text(),username=self.username.text(),email=self.email.text() or None,phone=self.phone.text() or None,password=self.password.text(),password_confirmation=self.confirmation.text(),template_code=str(code)))

    def show_error(self,message):
        self.error_label.setText(message); self.password.clear(); self.confirmation.clear()
