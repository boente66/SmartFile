from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QPushButton, QHBoxLayout, QScrollArea
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt


class PreviewWidget(QWidget):
    """
    Widget de preview grande com zoom.
    Reutilizável por PDF e Scanner.
    """

    def __init__(self):
        super().__init__()
        self._pixmap_original: QPixmap | None = None
        self._scale = 1.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Área com scroll
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.image_label)

        layout.addWidget(self.scroll)

        # Controles de zoom
        controls = QHBoxLayout()

        btn_zoom_in = QPushButton("+")
        btn_zoom_out = QPushButton("−")
        btn_reset = QPushButton("100%")

        btn_zoom_in.clicked.connect(self.zoom_in)
        btn_zoom_out.clicked.connect(self.zoom_out)
        btn_reset.clicked.connect(self.reset_zoom)

        controls.addWidget(btn_zoom_in)
        controls.addWidget(btn_zoom_out)
        controls.addWidget(btn_reset)
        controls.addStretch()

        layout.addLayout(controls)

    # -------------------------
    # API pública
    # -------------------------
    def set_pixmap(self, pixmap: QPixmap):
        self._pixmap_original = pixmap
        self._scale = 1.0
        self._update_view()

    def zoom_in(self):
        self._scale *= 1.2
        self._update_view()

    def zoom_out(self):
        self._scale /= 1.2
        self._update_view()

    def reset_zoom(self):
        self._scale = 1.0
        self._update_view()

    # -------------------------
    # Interno
    # -------------------------
    def _update_view(self):
        if self._pixmap_original is None or self._pixmap_original.isNull():
            self.image_label.clear()
            return

        scaled = self._pixmap_original.scaled(
            self._pixmap_original.size() * self._scale,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
