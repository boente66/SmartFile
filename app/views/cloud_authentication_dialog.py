from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextBrowser, QVBoxLayout,
)

from app.ui.icon_provider import IconProvider


class CloudAuthenticationDialog(QDialog):
    """Conduz o OAuth sem esconder do usuário a URL ou o código retornado."""

    PROVIDER_NAMES = {
        "ONEDRIVE": "Microsoft OneDrive",
        "GOOGLE_DRIVE": "Google Drive",
    }

    def __init__(self, provider: str, authorization_url: str, parent=None):
        super().__init__(parent)
        self.provider = provider
        self.authorization_url = authorization_url
        self.setWindowTitle(f"Conectar {self.PROVIDER_NAMES.get(provider, provider)}")
        self.setWindowIcon(IconProvider.icon("cloud_add"))
        self.resize(620, 430)
        self.setMinimumSize(520, 360)

        root = QVBoxLayout(self)
        title = QLabel(f"Autenticar com {self.PROVIDER_NAMES.get(provider, provider)}")
        title.setObjectName("authTitle")
        root.addWidget(title)

        instructions = QTextBrowser()
        instructions.setMaximumHeight(135)
        instructions.setHtml(
            "<ol>"
            "<li>Abra a página oficial de autenticação.</li>"
            "<li>Entre na conta e autorize o SmartFile.</li>"
            "<li>Copie o código retornado pelo provedor.</li>"
            "<li>Cole o código abaixo e selecione <b>Concluir autenticação</b>.</li>"
            "</ol>"
        )
        root.addWidget(instructions)

        form = QFormLayout()
        self.url_edit = QLineEdit(authorization_url)
        self.url_edit.setReadOnly(True)
        self.url_edit.setCursorPosition(0)
        form.addRow("Página oficial:", self.url_edit)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("Cole o código de autorização")
        self.code_edit.setClearButtonEnabled(True)
        form.addRow("Código retornado:", self.code_edit)
        root.addLayout(form)

        browser_actions = QHBoxLayout()
        self.open_browser_button = QPushButton("Abrir navegador")
        IconProvider.apply(self.open_browser_button, "cloud_add")
        self.open_browser_button.clicked.connect(self.open_browser)
        self.copy_link_button = QPushButton("Copiar link")
        self.copy_link_button.clicked.connect(self.copy_link)
        browser_actions.addWidget(self.open_browser_button)
        browser_actions.addWidget(self.copy_link_button)
        browser_actions.addStretch()
        root.addLayout(browser_actions)

        self.status_label = QLabel(
            "O SmartFile só salvará a conta depois que o código for validado."
        )
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.finish_button = self.buttons.addButton(
            "Concluir autenticação", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.finish_button.clicked.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def open_browser(self) -> bool:
        opened = QDesktopServices.openUrl(QUrl(self.authorization_url))
        if opened:
            self.status_label.setText(
                "Navegador aberto. Após autorizar, retorne ao SmartFile com o código."
            )
        else:
            self.status_label.setText(
                "Não foi possível abrir o navegador automaticamente. Copie o link."
            )
            QMessageBox.information(
                self,
                "Abrir navegador",
                "Copie o link e abra-o manualmente no navegador.",
            )
        return opened

    def copy_link(self) -> None:
        QGuiApplication.clipboard().setText(self.authorization_url)
        self.status_label.setText("Link copiado para a área de transferência.")

    def authorization_code(self) -> str:
        return self.code_edit.text().strip()

    def _accept_if_valid(self) -> None:
        if not self.authorization_code():
            self.status_label.setText("Cole o código retornado antes de continuar.")
            self.code_edit.setFocus()
            return
        self.accept()
