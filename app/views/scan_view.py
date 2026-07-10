from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QHBoxLayout
)
from PyQt6.QtCore import pyqtSignal as Signal, Qt, QSize
from PyQt6.QtGui import QIcon


class ScanView(QWidget):
    """
    View do Scanner com preview e seleção de dispositivo.
    """

    scan_requested = Signal()
    remove_requested = Signal(int)
    save_pdf_requested = Signal()
    device_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    # -------------------------
    # UI
    # -------------------------
    def _setup_ui(self):

        layout = QVBoxLayout(self)

        title = QLabel("Scanner")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        # -------------------------
        # Scanner device
        # -------------------------

        device_layout = QHBoxLayout()

        device_layout.addWidget(QLabel("Scanner"))

        self.device_combo = QComboBox()
        self.device_combo.currentTextChanged.connect(
            lambda text: self.device_changed.emit(text)
        )

        device_layout.addWidget(self.device_combo)

        layout.addLayout(device_layout)

        # -------------------------
        # DPI
        # -------------------------

        dpi_layout = QHBoxLayout()

        dpi_layout.addWidget(QLabel("DPI"))

        self.dpi_combo = QComboBox()
        self.dpi_combo.addItems([
            "150",
            "300",
            "600"
        ])

        self.dpi_combo.setCurrentText("300")

        dpi_layout.addWidget(self.dpi_combo)

        layout.addLayout(dpi_layout)

        # -------------------------
        # Color Mode
        # -------------------------

        color_layout = QHBoxLayout()

        color_layout.addWidget(QLabel("Modo"))

        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "color",
            "gray",
            "bw"
        ])

        color_layout.addWidget(self.color_combo)

        layout.addLayout(color_layout)

        # -------------------------
        # Preview pages
        # -------------------------

        self.page_list = QListWidget()
        self.page_list.setIconSize(QSize(120, 160))

        layout.addWidget(self.page_list)

        # -------------------------
        # Buttons
        # -------------------------

        btn_scan = QPushButton("Escanear Página")
        btn_scan.clicked.connect(lambda: self.scan_requested.emit())

        btn_remove = QPushButton("Excluir Página")
        btn_remove.clicked.connect(self._request_remove)

        btn_save = QPushButton("Salvar PDF")
        btn_save.clicked.connect(lambda: self.save_pdf_requested.emit())

        layout.addWidget(btn_scan)
        layout.addWidget(btn_remove)
        layout.addWidget(btn_save)

    # -------------------------
    # API DA VIEW
    # -------------------------

    def set_devices(self, devices: list[str]):

        self.device_combo.clear()

        if not devices:
            self.device_combo.addItem("Nenhum scanner encontrado")
            self.device_combo.setEnabled(False)
            return

        self.device_combo.setEnabled(True)

        for dev in devices:
            self.device_combo.addItem(dev)

    def add_thumbnail(self, pixmap):

        item = QListWidgetItem(
            f"Página {self.page_list.count() + 1}"
        )

        item.setIcon(
            QIcon(
                pixmap.scaled(
                    120,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )
        )

        self.page_list.addItem(item)

    def remove_thumbnail(self, index: int):
        self.page_list.takeItem(index)

    # -------------------------
    # Actions internas
    # -------------------------

    def _request_remove(self):

        row = self.page_list.currentRow()

        if row >= 0:
            self.remove_requested.emit(row)

    # -------------------------
    # Configuração do scan
    # -------------------------

    def get_scan_config(self) -> dict:

        return {
            "device": self.device_combo.currentText(),
            "dpi": int(self.dpi_combo.currentText()),
            "color": self.color_combo.currentText()
        }