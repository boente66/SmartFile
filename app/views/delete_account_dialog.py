from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


class DeleteAccountDialog(QDialog):
    """Confirma uma operação irreversível sem coletar dados além da senha atual."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Excluir minha conta")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)
        warning = QLabel(
            "Esta ação encerra todas as sessões, remove seus vínculos e anonimiza "
            "os dados da conta. Os documentos não serão apagados. Se houver outros "
            "membros em uma organização onde você é o único proprietário, será "
            "necessário transferir a propriedade primeiro."
        )
        warning.setWordWrap(True)
        warning.setObjectName("dangerNotice")
        root.addWidget(warning)
        form = QFormLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Informe sua senha atual")
        self.confirmation = QLineEdit()
        self.confirmation.setPlaceholderText("Digite EXCLUIR")
        form.addRow("Senha atual:", self.password)
        form.addRow("Confirmação:", self.confirmation)
        root.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Excluir conta")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def values(self) -> tuple[str, str]:
        return self.password.text(), self.confirmation.text()
