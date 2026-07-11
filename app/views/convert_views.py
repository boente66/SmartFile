# app/views/convert_view.py

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QFileDialog
)
from PyQt6.QtCore import pyqtSignal as Signal

from app.ui.icon_provider import IconProvider


class ConvertView(QWidget):
    """
    Tela de conversão de arquivos.

    View pura:
    - não conhece Controller
    - não conhece Service
    """

    convert_requested = Signal(dict)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    # -------------------------
    # UI
    # -------------------------
    def _setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Conversão de Arquivos")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        # -------------------------
        # INPUT
        # -------------------------

        self.input_edit = QLineEdit()

        btn_input = QPushButton("Abrir")
        IconProvider.apply(btn_input, "open")
        btn_input.clicked.connect(self._browse_input)

        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Arquivo de entrada"))
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(btn_input)

        layout.addLayout(input_layout)

        # -------------------------
        # FORMATO
        # -------------------------

        self.format_combo = QComboBox()

        self.format_combo.addItems([
            "PDF → DOCX",
            "DOCX → PDF",
            "JPG → PDF",
            "PDF → JPG",
            "XLSX → CSV",
            "CSV → XLSX",
            "TXT → PDF"
        ])

        format_layout = QHBoxLayout()
        format_layout.addWidget(QLabel("Formato de saída"))
        format_layout.addWidget(self.format_combo)

        layout.addLayout(format_layout)

        # -------------------------
        # OUTPUT
        # -------------------------

        self.output_edit = QLineEdit()

        btn_output = QPushButton("Salvar como")
        IconProvider.apply(btn_output, "save")
        btn_output.clicked.connect(self._browse_output)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Arquivo de saída"))
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(btn_output)

        layout.addLayout(output_layout)

        # -------------------------
        # CONVERT
        # -------------------------

        btn_convert = QPushButton("Converter")
        IconProvider.apply(btn_convert, "converter")
        btn_convert.setFixedHeight(36)
        btn_convert.clicked.connect(self._request_conversion)

        layout.addWidget(btn_convert)

        layout.addStretch()

    # -------------------------
    # UI Actions
    # -------------------------

    def set_input_path(self, path: str):
        self.input_edit.setText(path)

    def _browse_input(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo"
        )

        if path:
            self.input_edit.setText(path)

    def _browse_output(self):

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar arquivo"
        )

        if path:
            self.output_edit.setText(path)

    def _request_conversion(self):

        data = {
            "input": self.input_edit.text().strip(),
            "output": self.output_edit.text().strip(),
            "format": self.format_combo.currentText()
        }

        self.convert_requested.emit(data)
