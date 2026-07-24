from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class PasswordRecoveryDialog(QDialog):
    """Coleta somente os dados necessários à recuperação offline."""

    def __init__(self, suggested_login: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recuperar senha")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)
        explanation = QLabel(
            "Informe um código de recuperação salvo anteriormente. "
            "O SmartFile não envia códigos por e-mail nesta versão."
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        form = QFormLayout()
        self.login = QLineEdit(suggested_login)
        self.login.setPlaceholderText("Usuário ou e-mail")
        self.code = QLineEdit()
        self.code.setPlaceholderText("SF-XXXX-XXXX-XXXX-XXXX")
        self.code.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password.setPlaceholderText("Mínimo de 8 caracteres")
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation.setPlaceholderText("Repita a nova senha")
        form.addRow("Usuário ou e-mail:", self.login)
        form.addRow("Código de recuperação:", self.code)
        form.addRow("Nova senha:", self.new_password)
        form.addRow("Confirmar senha:", self.confirmation)
        root.addLayout(form)
        self.error = QLabel()
        self.error.setObjectName("authError")
        self.error.setWordWrap(True)
        root.addWidget(self.error)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Redefinir senha"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def accept(self) -> None:
        if not all(
            (
                self.login.text().strip(),
                self.code.text().strip(),
                self.new_password.text(),
                self.confirmation.text(),
            )
        ):
            self.error.setText("Preencha todos os campos.")
            return
        if len(self.new_password.text()) < 8:
            self.error.setText(
                "A nova senha deve possuir pelo menos 8 caracteres."
            )
            return
        if self.new_password.text() != self.confirmation.text():
            self.error.setText("As senhas não coincidem.")
            return
        super().accept()

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.login.text(),
            self.code.text(),
            self.new_password.text(),
            self.confirmation.text(),
        )
