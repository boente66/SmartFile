from __future__ import annotations

from PyQt6.QtCore import QAbstractAnimation, QPropertyAnimation, QTimer, Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.icon_provider import IconProvider


class ToastNotification(QFrame):
    """Notificação não modal, temporária e reutilizável da janela principal."""

    def __init__(
        self,
        parent: QWidget,
        *,
        title: str,
        message: str,
        timeout_ms: int = 6_000,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("toastNotification")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(380)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 12, 14)
        layout.setSpacing(12)

        icon = QLabel()
        icon.setObjectName("toastIcon")
        icon.setPixmap(IconProvider.colored_icon("user", "#16a34a").pixmap(26, 26))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(icon)

        copy = QVBoxLayout()
        copy.setSpacing(3)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("toastTitle")
        self.message_label = QLabel(message)
        self.message_label.setObjectName("toastMessage")
        self.message_label.setWordWrap(True)
        copy.addWidget(self.title_label)
        copy.addWidget(self.message_label)
        layout.addLayout(copy, 1)

        close_button = QToolButton()
        close_button.setObjectName("toastClose")
        close_button.setText("×")
        close_button.setToolTip("Fechar notificação")
        close_button.clicked.connect(self.dismiss)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignTop)

        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setDuration(180)
        self._fade.finished.connect(self.hide)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.dismiss)
        self._timer.start(max(1_500, timeout_ms))

    def show_toast(self) -> None:
        self.adjustSize()
        self.reposition()
        self.raise_()
        self.show()

    def reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        margin = 18
        self.move(max(margin, parent.width() - self.width() - margin), margin)

    def dismiss(self) -> None:
        if not self.isVisible() or self._fade.state() == QAbstractAnimation.State.Running:
            return
        self._timer.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(0.0)
        self._fade.start()
