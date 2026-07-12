from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QVBoxLayout, QWidget,
)

from app.models.handwritten_signature_request import HandwrittenSignatureRequest
from app.ui.icon_provider import IconProvider
from app.utils.file_naming import safe_output_path
from app.views.widgets.signature_canvas import SignatureCanvas
from app.views.widgets.signature_placement_widget import SignaturePlacementWidget


class HandwrittenSignatureDialog(QDialog):
    def __init__(
        self,
        input_path: Path,
        page_count: int,
        current_page: int,
        page_preview: QPixmap,
        page_size: tuple[float, float],
        rotation: int = 0,
        existing_signatures_confirmed: bool = False,
        page_preview_provider: Callable[[int], tuple[QPixmap, tuple[float, float]]] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.input_path = input_path
        self.page_size = page_size
        self.rotation = rotation
        self.existing_signatures_confirmed = existing_signatures_confirmed
        self._page_preview_provider = page_preview_provider
        self._position = (0.0, 0.0, 0.0, 0.0)
        self._signature_bytes = b""
        self.setWindowTitle("Assinatura manuscrita — marca visual")
        self.resize(940, 700)
        root = QVBoxLayout(self)
        warning = QLabel(
            "Esta é uma assinatura eletrônica visual. Ela não utiliza certificado e não possui validação criptográfica."
        )
        warning.setWordWrap(True)
        warning.setObjectName("handwrittenSignatureNotice")
        root.addWidget(warning)
        self.steps = QStackedWidget()
        root.addWidget(self.steps, 1)

        draw_page = QWidget()
        draw_layout = QVBoxLayout(draw_page)
        draw_layout.addWidget(QLabel("Desenhe dentro da área abaixo usando mouse, toque ou caneta:"))
        self.canvas = SignatureCanvas()
        draw_layout.addWidget(self.canvas, 1)
        tools = QHBoxLayout()
        undo = QPushButton("Desfazer"); undo.clicked.connect(self.canvas.undo)
        redo = QPushButton("Refazer"); redo.clicked.connect(self.canvas.redo)
        clear = QPushButton("Limpar"); IconProvider.apply(clear, "trash"); clear.clicked.connect(self.canvas.clear)
        self.thickness = QComboBox()
        for label, value in (("Fina", 2.0), ("Média", 3.5), ("Grossa", 6.0)):
            self.thickness.addItem(label, value)
        self.thickness.setCurrentIndex(1)
        self.thickness.currentIndexChanged.connect(lambda: self.canvas.set_stroke_width(float(self.thickness.currentData())))
        self.color = QComboBox(); self.color.addItem("Preta", "#111827"); self.color.addItem("Azul", "#1d4ed8")
        self.color.currentIndexChanged.connect(lambda: self.canvas.set_color(str(self.color.currentData())))
        for widget in (undo, redo, clear, QLabel("Espessura:"), self.thickness, QLabel("Cor:"), self.color):
            tools.addWidget(widget)
        tools.addStretch()
        next_button = QPushButton("Posicionar na página")
        next_button.clicked.connect(self._prepare_placement)
        tools.addWidget(next_button)
        draw_layout.addLayout(tools)
        self.steps.addWidget(draw_page)

        placement_page = QWidget()
        placement_layout = QHBoxLayout(placement_page)
        self.placement_container = QVBoxLayout()
        placement_layout.addLayout(self.placement_container, 1)
        fields = QFormLayout()
        self.page_spin = QSpinBox(); self.page_spin.setRange(1, max(1, page_count)); self.page_spin.setValue(current_page)
        self.page_spin.valueChanged.connect(self._change_page)
        self.signer_name = QLineEdit()
        self.caption = QCheckBox("Adicionar nome, data e ‘Assinado eletronicamente’")
        suggested = safe_output_path(input_path.with_name(f"{input_path.stem}_assinado_manualmente.pdf"))
        self.output_edit = QLineEdit(str(suggested))
        output_button = QPushButton("Salvar como…"); IconProvider.apply(output_button, "save"); output_button.clicked.connect(self._choose_output)
        output_row = QHBoxLayout(); output_row.addWidget(self.output_edit, 1); output_row.addWidget(output_button)
        fields.addRow("Página:", self.page_spin)
        fields.addRow("Nome:", self.signer_name)
        fields.addRow("Legenda:", self.caption)
        fields.addRow("Novo PDF:", output_row)
        back = QPushButton("Voltar ao desenho"); back.clicked.connect(lambda: self.steps.setCurrentIndex(0))
        fields.addRow(back)
        placement_layout.addLayout(fields)
        self.steps.addWidget(placement_page)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar novo PDF")
        buttons.accepted.connect(self._accept_if_ready)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._page_preview = page_preview
        self.canvas.set_stroke_width(float(self.thickness.currentData()))

    def build_request(self) -> HandwrittenSignatureRequest:
        x, y, width, height = self._position
        return HandwrittenSignatureRequest(
            input_path=self.input_path,
            output_path=Path(self.output_edit.text()),
            page_number=self.page_spin.value(),
            x=x, y=y, width=width, height=height,
            signature_image=self._signature_bytes,
            signer_name=self.signer_name.text().strip() or None,
            signed_at=datetime.now().astimezone(),
            color=self.canvas.color_name,
            stroke_width=self.canvas.stroke_width,
            add_caption=self.caption.isChecked(),
            existing_signatures_confirmed=self.existing_signatures_confirmed,
        )

    def clear_signature(self) -> None:
        self._signature_bytes = b""
        self.canvas.clear()

    def _prepare_placement(self) -> None:
        data = self.canvas.export_png()
        if not data:
            QMessageBox.warning(self, "Assinatura manuscrita", "Desenhe a assinatura antes de continuar.")
            return
        self._signature_bytes = data
        signature = QPixmap(); signature.loadFromData(data, "PNG")
        self._replace_placement(signature)

    def _replace_placement(self, signature: QPixmap) -> None:
        if hasattr(self, "placement"):
            self.placement_container.removeWidget(self.placement)
            self.placement.deleteLater()
        self.placement = SignaturePlacementWidget(
            self._page_preview, signature, self.page_size, self.rotation
        )
        self.placement.position_changed.connect(self._set_position)
        self.placement_container.insertWidget(0, self.placement, 1)
        self.steps.setCurrentIndex(1)

    def _change_page(self, page_number: int) -> None:
        if self._page_preview_provider is None:
            return
        try:
            self._page_preview, self.page_size = self._page_preview_provider(page_number)
        except Exception as exc:
            QMessageBox.warning(self, "Visualização da página", str(exc))
            return
        if self._signature_bytes:
            signature = QPixmap(); signature.loadFromData(self._signature_bytes, "PNG")
            self._replace_placement(signature)

    def _set_position(self, x: float, y: float, width: float, height: float) -> None:
        self._position = (x, y, width, height)

    def _accept_if_ready(self) -> None:
        if self.steps.currentIndex() == 0 or not self._signature_bytes:
            QMessageBox.warning(self, "Assinatura manuscrita", "Desenhe e posicione a assinatura antes de salvar.")
            return
        if self._position[2] <= 0 or self._position[3] <= 0:
            QMessageBox.warning(self, "Assinatura manuscrita", "Defina uma posição válida na página.")
            return
        self.accept()

    def _choose_output(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Salvar novo PDF", self.output_edit.text(), "PDF (*.pdf)")
        if path:
            self.output_edit.setText(path)
