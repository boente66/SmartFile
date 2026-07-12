from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.icon_provider import IconProvider
from app.views.widgets.preview_widget import PreviewWidget


class ScanView(QWidget):
    """Interface do scanner; coleta configuração e emite intenções do usuário."""

    scan_requested = pyqtSignal()
    remove_requested = pyqtSignal(int)
    save_pdf_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    refresh_devices_requested = pyqtSignal()
    device_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._pixmaps: list[QPixmap] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(16)

        title = QLabel("Scanner")
        title.setObjectName("title")
        root.addWidget(title)
        subtitle = QLabel("Digitalize documentos e salve as páginas em PDF.")
        subtitle.setObjectName("scanSubtitle")
        root.addWidget(subtitle)

        root.addWidget(self._build_device_bar())

        content = QHBoxLayout()
        content.setSpacing(14)
        content.addWidget(self._build_settings_panel(), 2)
        content.addWidget(self._build_preview_panel(), 5)
        content.addWidget(self._build_pages_panel(), 3)
        root.addLayout(content, 1)

    def _build_device_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("scanToolbar")
        layout = QGridLayout(bar)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setHorizontalSpacing(12)

        layout.addWidget(QLabel("Dispositivo"), 0, 0)
        self.device_combo = QComboBox()
        self.device_combo.currentTextChanged.connect(self.device_changed.emit)
        layout.addWidget(self.device_combo, 1, 0)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setToolTip("Atualizar dispositivos")
        IconProvider.apply(self.btn_refresh, "scan")
        self.btn_refresh.clicked.connect(self.refresh_devices_requested.emit)
        layout.addWidget(self.btn_refresh, 1, 1)

        layout.addWidget(QLabel("Perfil"), 0, 2)
        self.profile_combo = QComboBox()
        self.profile_combo.addItem("Documento colorido", "color")
        self.profile_combo.addItem("Documento em tons de cinza", "gray")
        self.profile_combo.addItem("Documento em preto e branco", "bw")
        layout.addWidget(self.profile_combo, 1, 2)

        layout.addWidget(QLabel("Fonte de papel"), 0, 3)
        self.source_combo = QComboBox()
        self.source_combo.addItem("Detectando fontes…", None)
        self.source_combo.setEnabled(False)
        self.source_combo.setToolTip("Fonte física utilizada na digitalização")
        layout.addWidget(self.source_combo, 1, 3)

        layout.addWidget(QLabel("Resolução"), 0, 4)
        self.dpi_combo = QComboBox()
        for dpi in (150, 300, 600):
            self.dpi_combo.addItem(f"{dpi} dpi", dpi)
        self.dpi_combo.setCurrentIndex(1)
        layout.addWidget(self.dpi_combo, 1, 4)
        layout.setColumnStretch(0, 3)
        layout.setColumnStretch(2, 2)
        layout.setColumnStretch(3, 2)
        layout.setColumnStretch(4, 2)
        return bar

    def _build_settings_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("scanPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("Configurações")
        heading.setObjectName("scanSectionTitle")
        layout.addWidget(heading)
        layout.addWidget(self._separator())

        layout.addWidget(QLabel("Modo de cor"))
        self.color_combo = QComboBox()
        self.color_combo.addItem("Colorido", "color")
        self.color_combo.addItem("Tons de cinza", "gray")
        self.color_combo.addItem("Preto e branco", "bw")
        self.profile_combo.currentIndexChanged.connect(self.color_combo.setCurrentIndex)
        self.color_combo.currentIndexChanged.connect(self.profile_combo.setCurrentIndex)
        layout.addWidget(self.color_combo)

        layout.addWidget(QLabel("Tamanho do papel"))
        self.paper_combo = QComboBox()
        self.paper_combo.addItem("A4 (210 × 297 mm)")
        self.paper_combo.setEnabled(False)
        self.paper_combo.setToolTip("Configuração preparada para suporte futuro do backend")
        layout.addWidget(self.paper_combo)

        note = QLabel(
            "As opções disponíveis são aplicadas pelo backend SANE ou TWAIN do dispositivo selecionado."
        )
        note.setObjectName("scanHint")
        note.setWordWrap(True)
        layout.addWidget(note)
        layout.addStretch()

        self.btn_scan = QPushButton("Digitalizar")
        self.btn_scan.setObjectName("primary")
        IconProvider.apply(self.btn_scan, "scan")
        self.btn_scan.clicked.connect(self.scan_requested.emit)
        layout.addWidget(self.btn_scan)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("scanPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        heading = QLabel("Visualização")
        heading.setObjectName("scanSectionTitle")
        self.page_indicator = QLabel("Nenhuma página")
        self.page_indicator.setObjectName("scanHint")
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self.page_indicator)
        layout.addLayout(header)

        self.preview = PreviewWidget()
        self.preview.setObjectName("scanPreview")
        layout.addWidget(self.preview, 1)

        actions = QHBoxLayout()
        self.btn_scan_more = QPushButton("Digitalizar e adicionar mais")
        IconProvider.apply(self.btn_scan_more, "scan")
        self.btn_scan_more.clicked.connect(self.scan_requested.emit)
        self.btn_clear = QPushButton("Cancelar sessão")
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        actions.addWidget(self.btn_scan_more, 1)
        actions.addWidget(self.btn_clear)
        layout.addLayout(actions)
        return panel

    def _build_pages_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("scanPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.pages_title = QLabel("Páginas digitalizadas (0)")
        self.pages_title.setObjectName("scanSectionTitle")
        self.btn_remove = QPushButton()
        self.btn_remove.setToolTip("Remover página selecionada")
        IconProvider.apply(self.btn_remove, "trash")
        self.btn_remove.clicked.connect(self._request_remove)
        header.addWidget(self.pages_title)
        header.addStretch()
        header.addWidget(self.btn_remove)
        layout.addLayout(header)

        self.page_list = QListWidget()
        self.page_list.setViewMode(QListView.ViewMode.IconMode)
        self.page_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.page_list.setMovement(QListView.Movement.Static)
        self.page_list.setIconSize(QSize(120, 160))
        self.page_list.setGridSize(QSize(142, 195))
        self.page_list.currentRowChanged.connect(self._show_selected_page)
        layout.addWidget(self.page_list, 1)

        layout.addWidget(self._separator())
        output_title = QLabel("Saída")
        output_title.setObjectName("scanSectionTitle")
        layout.addWidget(output_title)
        layout.addWidget(QLabel("Salvar como"))
        self.output_format_combo = QComboBox()
        self.output_format_combo.addItem("PDF")
        self.output_format_combo.setEnabled(False)
        layout.addWidget(self.output_format_combo)

        self.btn_save = QPushButton("Salvar documento")
        self.btn_save.setObjectName("primary")
        IconProvider.apply(self.btn_save, "save")
        self.btn_save.clicked.connect(self.save_pdf_requested.emit)
        layout.addWidget(self.btn_save)
        self._update_state()
        return panel

    @staticmethod
    def _separator() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("scanSeparator")
        return line

    def set_devices(self, devices: list[str]) -> None:
        self.device_combo.clear()
        if not devices:
            self.device_combo.addItem("Nenhum scanner encontrado")
            self.device_combo.setEnabled(False)
            self.btn_scan.setEnabled(False)
            self.btn_scan_more.setEnabled(False)
            return
        self.device_combo.setEnabled(True)
        self.btn_scan.setEnabled(True)
        self.btn_scan_more.setEnabled(True)
        self.device_combo.addItems(devices)

    def set_sources(self, sources: list[tuple[str, str]]) -> None:
        """Preenche as fontes usando (rótulo amigável, valor do backend)."""
        self.source_combo.clear()
        if not sources:
            self.source_combo.addItem("Fonte automática", None)
            self.source_combo.setEnabled(False)
            return
        for label, backend_value in sources:
            self.source_combo.addItem(label, backend_value)
        self.source_combo.setEnabled(len(sources) > 1)
        flatbed_index = next(
            (
                index
                for index, (_label, value) in enumerate(sources)
                if "flatbed" in value.lower() or "platen" in value.lower()
            ),
            0,
        )
        self.source_combo.setCurrentIndex(flatbed_index)

    def add_thumbnail(self, pixmap: QPixmap) -> None:
        self._pixmaps.append(pixmap)
        item = QListWidgetItem(f"Página {len(self._pixmaps)}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        item.setIcon(
            QIcon(
                pixmap.scaled(
                    120,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        )
        self.page_list.addItem(item)
        self.page_list.setCurrentRow(len(self._pixmaps) - 1)
        self._update_state()

    def remove_thumbnail(self, index: int) -> None:
        if 0 <= index < len(self._pixmaps):
            self._pixmaps.pop(index)
            self.page_list.takeItem(index)
            self._renumber_pages()
        self._update_state()

    def clear_pages(self) -> None:
        self._pixmaps.clear()
        self.page_list.clear()
        self.preview.set_pixmap(QPixmap())
        self._update_state()

    def get_scan_config(self) -> dict:
        return {
            "device": self.device_combo.currentText() if self.device_combo.isEnabled() else "",
            "dpi": int(self.dpi_combo.currentData()),
            "color": str(self.color_combo.currentData()),
            "source": self.source_combo.currentData(),
        }

    def _request_remove(self) -> None:
        row = self.page_list.currentRow()
        if row >= 0:
            self.remove_requested.emit(row)

    def _show_selected_page(self, index: int) -> None:
        if 0 <= index < len(self._pixmaps):
            self.preview.set_pixmap(self._pixmaps[index])
            self.page_indicator.setText(f"Página {index + 1} de {len(self._pixmaps)}")
        elif not self._pixmaps:
            self.preview.set_pixmap(QPixmap())
            self.page_indicator.setText("Nenhuma página")

    def _renumber_pages(self) -> None:
        for index in range(self.page_list.count()):
            self.page_list.item(index).setText(f"Página {index + 1}")
        if self._pixmaps:
            self.page_list.setCurrentRow(min(self.page_list.currentRow(), len(self._pixmaps) - 1))

    def _update_state(self) -> None:
        count = len(self._pixmaps)
        self.pages_title.setText(f"Páginas digitalizadas ({count})")
        self.btn_remove.setEnabled(count > 0)
        self.btn_save.setEnabled(count > 0)
        self.btn_clear.setEnabled(count > 0)
        if not count:
            self.page_indicator.setText("Nenhuma página")
