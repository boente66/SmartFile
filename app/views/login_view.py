from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider


class LoginView(QWidget):
    login_requested = pyqtSignal(str, str, bool)
    create_account_requested = pyqtSignal()

    def __init__(self, allow_registration: bool = True):
        super().__init__(); self.allow_registration = allow_registration; self.setObjectName("authWindow"); self.setWindowTitle("SmartFile — Login")
        self.resize(1100, 700); self.setMinimumSize(820, 560); self.setWindowIcon(IconProvider.icon("app"))
        root=QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._brand_panel(), 4); root.addWidget(self._form_panel(), 6)

    def _brand_panel(self):
        panel=QWidget(); panel.setObjectName("authBrandPanel"); layout=QVBoxLayout(panel); layout.setContentsMargins(55,70,55,55)
        logo=QLabel("☁  SmartFile"); logo.setObjectName("authBrandLogo"); layout.addWidget(logo)
        subtitle=QLabel("Seu gerenciamento de documentos\ninteligente e seguro."); subtitle.setObjectName("authBrandSubtitle"); subtitle.setWordWrap(True); layout.addWidget(subtitle)
        layout.addStretch();
        for title,text in (("Seguro","Seus documentos protegidos com armazenamento interno seguro."),("Sincronizado","Sincronização em nuvem opcional e offline-first."),("Produtivo","Ferramentas completas para organizar e transformar PDF.")):
            label=QLabel(f"✓  {title}\n    {text}"); label.setObjectName("authFeature"); label.setWordWrap(True); layout.addWidget(label)
        layout.addStretch(); return panel

    def _form_panel(self):
        outer=QWidget(); outer.setObjectName("authFormBackground"); layout=QVBoxLayout(outer); layout.setContentsMargins(100,80,100,80)
        card=QWidget(); card.setObjectName("authCard"); form=QVBoxLayout(card); form.setContentsMargins(48,42,48,42); form.setSpacing(13)
        title=QLabel("Bem-vindo ao SmartFile"); title.setObjectName("authTitle"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); form.addWidget(title)
        caption=QLabel("Faça login para continuar"); caption.setObjectName("authCaption"); caption.setAlignment(Qt.AlignmentFlag.AlignCenter); form.addWidget(caption)
        form.addSpacing(20); form.addWidget(QLabel("Usuário ou e-mail")); self.login_edit=QLineEdit(); self.login_edit.setPlaceholderText("Digite seu usuário ou e-mail"); form.addWidget(self.login_edit)
        form.addWidget(QLabel("Senha")); self.password_edit=QLineEdit(); self.password_edit.setEchoMode(QLineEdit.EchoMode.Password); self.password_edit.setPlaceholderText("Digite sua senha"); self.password_edit.returnPressed.connect(self._submit); form.addWidget(self.password_edit)
        toggle=self.password_edit.addAction(IconProvider.icon("visualize"),QLineEdit.ActionPosition.TrailingPosition); toggle.setToolTip("Mostrar ou ocultar senha"); toggle.triggered.connect(lambda: self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal if self.password_edit.echoMode()==QLineEdit.EchoMode.Password else QLineEdit.EchoMode.Password))
        row=QHBoxLayout(); self.remember=QCheckBox("Lembrar de mim neste dispositivo"); row.addWidget(self.remember); row.addStretch(); form.addLayout(row)
        self.remember.hide()
        self.error_label=QLabel(""); self.error_label.setObjectName("authError"); self.error_label.setWordWrap(True); form.addWidget(self.error_label)
        button=QPushButton("Entrar"); button.setObjectName("authPrimary"); IconProvider.apply(button,"login"); button.clicked.connect(self._submit); form.addWidget(button)
        if self.allow_registration:
            register_row = QHBoxLayout()
            register_row.addStretch()
            register_row.addWidget(QLabel("Ainda não tem uma conta?"))
            register_button = QPushButton("Criar conta")
            register_button.setObjectName("authLinkButton")
            register_button.setFlat(True)
            register_button.clicked.connect(self.create_account_requested)
            register_row.addWidget(register_button)
            register_row.addStretch()
            form.addLayout(register_row)
        layout.addStretch(); layout.addWidget(card); layout.addStretch(); return outer

    def _submit(self):
        self.error_label.clear(); self.login_requested.emit(self.login_edit.text(),self.password_edit.text(),self.remember.isChecked())

    def show_error(self,message):
        self.error_label.setText(message); self.password_edit.clear(); self.password_edit.setFocus()
