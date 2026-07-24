from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)


class RecoveryCodesDialog(QDialog):
    """Exibe códigos apenas no momento em que são gerados."""

    def __init__(self, codes: tuple[str, ...], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Códigos de recuperação")
        self.setMinimumSize(480, 440)
        self._codes = tuple(codes)
        root = QVBoxLayout(self)
        title = QLabel("Guarde estes códigos em um local seguro")
        title.setStyleSheet("font-size: 17px; font-weight: 700;")
        root.addWidget(title)
        note = QLabel(
            "Cada código pode ser usado uma única vez para redefinir sua senha. "
            "Eles não poderão ser exibidos novamente pelo SmartFile."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        self.codes = QTextEdit()
        self.codes.setReadOnly(True)
        self.codes.setPlainText("\n".join(self._codes))
        self.codes.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        root.addWidget(self.codes)
        copy_button = QPushButton("Copiar códigos")
        copy_button.clicked.connect(self.copy_codes)
        root.addWidget(copy_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        root.addWidget(buttons)

    def copy_codes(self) -> None:
        QGuiApplication.clipboard().setText("\n".join(self._codes))
