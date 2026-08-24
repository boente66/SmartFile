from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.services.signature_image_service import SignatureImageService
from app.ui.icon_provider import IconProvider
from app.views.widgets.signature_canvas import SignatureCanvas


class SignatureAcquisitionWidget(QWidget):
    """Aquisição neutra de assinatura visual desenhada ou importada."""

    changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.normalizer = SignatureImageService()
        self._imported = b""
        self._method = "DRAWN"
        root = QVBoxLayout(self)
        choices = QHBoxLayout()
        self.draw_button = QPushButton("Assinar à mão")
        IconProvider.apply(self.draw_button, "viewer_handwritten_sign")
        self.import_button = QPushButton("Importar imagem")
        IconProvider.apply(self.import_button, "image")
        choices.addWidget(self.draw_button)
        choices.addWidget(self.import_button)
        choices.addStretch()
        root.addLayout(choices)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        drawn = QWidget()
        drawn_layout = QVBoxLayout(drawn)
        self.canvas = SignatureCanvas()
        drawn_layout.addWidget(self.canvas, 1)
        tools = QHBoxLayout()
        undo = QPushButton("Desfazer")
        redo = QPushButton("Refazer")
        clear = QPushButton("Limpar")
        undo.clicked.connect(self.canvas.undo)
        redo.clicked.connect(self.canvas.redo)
        clear.clicked.connect(self.canvas.clear)
        self.thickness = QComboBox()
        for label, value in (("Fina", 2.0), ("Média", 3.5), ("Grossa", 6.0)):
            self.thickness.addItem(label, value)
        self.thickness.setCurrentIndex(1)
        self.color = QComboBox()
        self.color.addItem("Preta", "#111827")
        self.color.addItem("Azul", "#1d4ed8")
        for widget in (
            undo, redo, clear, QLabel("Espessura:"), self.thickness,
            QLabel("Cor:"), self.color,
        ):
            tools.addWidget(widget)
        tools.addStretch()
        drawn_layout.addLayout(tools)
        self.pages.addWidget(drawn)

        imported = QWidget()
        imported_layout = QVBoxLayout(imported)
        self.preview = QLabel("Selecione uma imagem PNG, JPEG ou WEBP.")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(210)
        self.preview.setObjectName("signatureImagePreview")
        choose = QPushButton("Selecionar imagem…")
        IconProvider.apply(choose, "image")
        choose.clicked.connect(self._choose_image)
        imported_layout.addWidget(self.preview, 1)
        imported_layout.addWidget(choose)
        self.pages.addWidget(imported)

        self.draw_button.clicked.connect(lambda: self._select(0))
        self.import_button.clicked.connect(lambda: self._select(1))
        self.canvas.changed.connect(self.changed.emit)
        self.thickness.currentIndexChanged.connect(
            lambda: self.canvas.set_stroke_width(float(self.thickness.currentData()))
        )
        self.color.currentIndexChanged.connect(
            lambda: self.canvas.set_color(str(self.color.currentData()))
        )
        self.canvas.set_stroke_width(float(self.thickness.currentData()))

    @property
    def method(self) -> str:
        return self._method

    @property
    def color_name(self) -> str:
        return self.canvas.color_name

    @property
    def stroke_width(self) -> float:
        return self.canvas.stroke_width

    def signature_bytes(self) -> bytes:
        if self._method == "DRAWN":
            return self.canvas.export_png()
        return self._imported

    def clear(self) -> None:
        self.canvas.clear()
        self._imported = b""
        self.preview.setPixmap(QPixmap())
        self.preview.setText("Selecione uma imagem PNG, JPEG ou WEBP.")
        self.changed.emit(False)

    def _select(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self._method = "DRAWN" if index == 0 else "IMPORTED_IMAGE"
        self.changed.emit(bool(self.signature_bytes()))

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar assinatura visual", "",
            "Imagens (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        try:
            with open(path, "rb") as handle:
                data = handle.read(SignatureImageService.MAX_INPUT_SIZE + 1)
            self._imported = self.normalizer.normalize(data)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Importar assinatura", str(exc))
            return
        pixmap = QPixmap()
        pixmap.loadFromData(self._imported, "PNG")
        self.preview.setText("")
        self.preview.setPixmap(
            pixmap.scaled(
                520, 210, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.changed.emit(True)

