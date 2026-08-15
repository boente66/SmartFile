from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListView, QListWidget, QListWidgetItem, QMenu, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider
from app.views.widgets.preview_widget import PreviewWidget


class CapturePdfView(QWidget):
    """Experiência única para capturar, organizar e gerar documentos PDF."""

    scan_requested = pyqtSignal()
    import_images_requested = pyqtSignal(list)
    open_pdf_requested = pyqtSignal(str)
    add_pdfs_requested = pyqtSignal(list)
    remove_requested = pyqtSignal(list)
    reorder_requested = pyqtSignal(list)
    rotate_requested = pyqtSignal(list, int)
    extract_requested = pyqtSignal(list, str)
    split_requested = pyqtSignal(str)
    save_requested = pyqtSignal(str)
    add_to_ged_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    refresh_devices_requested = pyqtSignal()
    device_changed = pyqtSignal(str)
    current_page_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("capturePdf")
        self._pixmaps: dict[str, QPixmap] = {}
        self._building_pages = False
        self._setup_ui()
        self._connect_shortcuts()
        self.set_document_state("Novo documento", 0, False)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("capturePdfSplitter")
        splitter.addWidget(self._build_scan_panel())
        splitter.addWidget(self._build_pages_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.setSizes([280, 210, 760])
        splitter.setStretchFactor(2, 1)
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(1, True)
        self.splitter = splitter
        root.addWidget(splitter, 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QFrame(); header.setObjectName("capturePdfHeader")
        layout = QHBoxLayout(header); layout.setContentsMargins(18, 10, 18, 10); layout.setSpacing(12)
        identity = QVBoxLayout()
        title = QLabel("Captura e PDF"); title.setObjectName("capturePdfTitle")
        subtitle = QLabel("Digitalize, organize e prepare seus documentos")
        subtitle.setObjectName("capturePdfSubtitle")
        identity.addWidget(title); identity.addWidget(subtitle)
        layout.addLayout(identity)
        layout.addSpacing(20)
        self.btn_scan_top = self._toolbar_button("Digitalizar", "scan", self.scan_requested.emit)
        self.btn_import_top = self._toolbar_button("Importar", "import", self._choose_images)
        self.btn_open_top = self._toolbar_button("Abrir PDF", "open", self._choose_open_pdf)
        self.btn_add_top = QToolButton(); self.btn_add_top.setObjectName("capturePdfToolbarButton")
        self.btn_add_top.setText("Adicionar"); self.btn_add_top.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.btn_add_top.setIcon(IconProvider.icon("pdf_add")); self.btn_add_top.setIconSize(QSize(24, 24))
        self.btn_add_top.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QMenu(self.btn_add_top)
        self._menu_action(add_menu, "Digitalizar nova página", "scan", self.scan_requested.emit)
        self._menu_action(add_menu, "Importar imagens", "image", self._choose_images)
        self._menu_action(add_menu, "Adicionar outro PDF", "pdf_add", self._choose_add_pdfs)
        self.btn_add_top.setMenu(add_menu)
        for button in (self.btn_scan_top, self.btn_import_top, self.btn_open_top, self.btn_add_top):
            layout.addWidget(button)
        layout.addStretch()
        self.origin_label = QLabel("Origem selecionada: —")
        self.origin_label.setObjectName("capturePdfOrigin")
        layout.addWidget(self.origin_label)
        self.btn_refresh = QPushButton(); self.btn_refresh.setToolTip("Atualizar scanners")
        IconProvider.apply(self.btn_refresh, "scanner")
        self.btn_refresh.clicked.connect(self.refresh_devices_requested.emit)
        layout.addWidget(self.btn_refresh)
        return header

    def _build_scan_panel(self) -> QWidget:
        scroll = QScrollArea(); scroll.setObjectName("capturePdfScanScroll")
        scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel = QFrame(); panel.setObjectName("capturePdfPanel")
        panel.setMinimumWidth(235)
        layout = QVBoxLayout(panel); layout.setContentsMargins(14, 14, 14, 14); layout.setSpacing(9)
        layout.addWidget(self._heading("DIGITALIZAÇÃO"))
        self.device_combo = self._combo(); self.device_combo.currentTextChanged.connect(self._device_selected)
        self.profile_combo = self._combo()
        self.profile_combo.addItem("Documento (300 dpi)", "color")
        self.profile_combo.addItem("Tons de cinza", "gray")
        self.profile_combo.addItem("Preto e branco", "bw")
        self.color_combo = self._combo()
        self.color_combo.addItem("Colorido", "color"); self.color_combo.addItem("Tons de cinza", "gray"); self.color_combo.addItem("Preto e branco", "bw")
        self.profile_combo.currentIndexChanged.connect(self.color_combo.setCurrentIndex)
        self.color_combo.currentIndexChanged.connect(self.profile_combo.setCurrentIndex)
        self.dpi_combo = self._combo()
        for dpi in (150, 300, 600): self.dpi_combo.addItem(f"{dpi} dpi", dpi)
        self.dpi_combo.setCurrentIndex(1)
        self.paper_combo = self._combo(); self.paper_combo.addItem("A4 (210 × 297 mm)"); self.paper_combo.setEnabled(False)
        self.source_combo = self._combo(); self.source_combo.currentIndexChanged.connect(self._update_capabilities)
        for label, widget in (("Scanner:", self.device_combo), ("Perfil:", self.profile_combo), ("Cor:", self.color_combo), ("Resolução:", self.dpi_combo), ("Tamanho:", self.paper_combo), ("Fonte:", self.source_combo)):
            layout.addWidget(QLabel(label)); layout.addWidget(widget)
        self.duplex = QCheckBox("Frente e verso (duplex)")
        self.adf = QCheckBox("Alimentador automático")
        self.duplex.hide(); self.adf.hide(); layout.addWidget(self.duplex); layout.addWidget(self.adf)
        self.btn_scan = QPushButton("Iniciar Digitalização"); self.btn_scan.setObjectName("capturePdfPrimary")
        IconProvider.apply(self.btn_scan, "scan"); self.btn_scan.clicked.connect(self.scan_requested.emit)
        layout.addWidget(self.btn_scan)
        layout.addSpacing(8); layout.addWidget(self._heading("OUTRAS OPÇÕES"))
        layout.addWidget(self._wide_button("Importar Imagens", "image", self._choose_images))
        layout.addWidget(self._wide_button("Abrir PDF Existente", "pdf", self._choose_open_pdf))
        layout.addWidget(self._wide_button("Limpar Tudo", "trash", self.clear_requested.emit))
        hint = QLabel("Arraste e solte as páginas para reordenar.")
        hint.setObjectName("capturePdfHint"); hint.setWordWrap(True); layout.addWidget(hint)
        layout.addStretch()
        scroll.setWidget(panel)
        return scroll

    def _build_pages_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("capturePdfPanel"); panel.setMinimumWidth(180)
        layout = QVBoxLayout(panel); layout.setContentsMargins(10, 10, 10, 10)
        self.pages_heading = self._heading("PÁGINAS (0)"); layout.addWidget(self.pages_heading)
        self.page_list = QListWidget(); self.page_list.setObjectName("capturePdfPages")
        self.page_list.setViewMode(QListView.ViewMode.IconMode)
        self.page_list.setFlow(QListView.Flow.TopToBottom); self.page_list.setWrapping(False)
        self.page_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.page_list.setIconSize(QSize(115, 145)); self.page_list.setGridSize(QSize(145, 180))
        self.page_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.page_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.page_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.page_list.currentRowChanged.connect(self._current_changed)
        self.page_list.model().rowsMoved.connect(self._rows_moved)
        layout.addWidget(self.page_list, 1)
        buttons = QHBoxLayout()
        for tooltip, icon, callback in (("Mover para cima", "up", lambda: self._move(-1)), ("Mover para baixo", "down", lambda: self._move(1)), ("Remover", "trash", self._request_remove)):
            button = QPushButton(); button.setToolTip(tooltip); IconProvider.apply(button, icon); button.clicked.connect(callback); buttons.addWidget(button)
        layout.addLayout(buttons)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("capturePdfPreviewPanel")
        layout = QVBoxLayout(panel); layout.setContentsMargins(8, 8, 8, 8); layout.setSpacing(6)
        tools = QHBoxLayout(); tools.setSpacing(4)
        specs = (
            ("Girar à esquerda", "viewer_rotate_left", lambda: self._request_rotate(-90)),
            ("Girar à direita", "viewer_rotate_right", lambda: self._request_rotate(90)),
            ("Remover", "pdf_remove", self._request_remove),
            ("Extrair", "pdf_extract", self._request_extract),
            ("Reordenar", "pdf_move", self.page_list.setFocus),
            ("Mesclar", "pdf_merge", self._choose_add_pdfs),
        )
        self.document_actions: list[QPushButton] = []
        for text, icon, callback in specs:
            button = self._compact_action(text, icon, callback); tools.addWidget(button); self.document_actions.append(button)
        more = QToolButton(); more.setObjectName("capturePdfAction"); more.setText("Mais")
        more.setIcon(IconProvider.icon("more")); more.setIconSize(QSize(18, 18))
        more.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(more)
        self._menu_action(more_menu, "Dividir em arquivos individuais", "pdf_split", self._choose_split_directory)
        self._menu_action(more_menu, "Limpar workspace", "trash", self.clear_requested.emit)
        more.setMenu(more_menu); tools.addWidget(more); tools.addStretch()
        layout.addLayout(tools)
        self.preview = PreviewWidget(); self.preview.setObjectName("capturePdfPreview")
        layout.addWidget(self.preview, 1)
        navigation = QHBoxLayout()
        self.btn_first = self._nav("Primeira página", "viewer_first_page", lambda: self.page_list.setCurrentRow(0))
        self.btn_prev = self._nav("Página anterior", "viewer_previous_page", lambda: self._step(-1))
        self.page_indicator = QLabel("0 / 0"); self.page_indicator.setObjectName("capturePdfPageIndicator")
        self.btn_next = self._nav("Próxima página", "viewer_next_page", lambda: self._step(1))
        self.btn_last = self._nav("Última página", "viewer_last_page", lambda: self.page_list.setCurrentRow(self.page_list.count() - 1))
        navigation.addStretch()
        for item in (self.btn_first, self.btn_prev, self.page_indicator, self.btn_next, self.btn_last): navigation.addWidget(item)
        navigation.addStretch(); layout.addLayout(navigation)
        return panel

    def _build_footer(self) -> QWidget:
        footer = QFrame(); footer.setObjectName("capturePdfFooter")
        layout = QHBoxLayout(footer); layout.setContentsMargins(18, 10, 18, 10)
        self.document_label = QLabel("Documento: Novo documento")
        self.count_label = QLabel("Páginas: 0")
        layout.addWidget(self.document_label); layout.addStretch(); layout.addWidget(self.count_label); layout.addSpacing(24)
        self.btn_save = QPushButton("Salvar PDF..."); IconProvider.apply(self.btn_save, "pdf_save")
        self.btn_save.clicked.connect(self._choose_save)
        self.btn_ged = QPushButton("Adicionar ao SmartFile..."); self.btn_ged.setObjectName("capturePdfGed")
        IconProvider.apply(self.btn_ged, "import"); self.btn_ged.clicked.connect(self.add_to_ged_requested.emit)
        layout.addWidget(self.btn_save); layout.addWidget(self.btn_ged)
        return footer

    def set_devices(self, devices: list[str]) -> None:
        self.device_combo.blockSignals(True); self.device_combo.clear()
        if devices:
            self.device_combo.addItems(devices); self.device_combo.setEnabled(True)
        else:
            self.device_combo.addItem("Nenhum scanner encontrado"); self.device_combo.setEnabled(False)
        self.device_combo.blockSignals(False)
        self.btn_scan.setEnabled(bool(devices)); self.btn_scan_top.setEnabled(bool(devices))
        self.origin_label.setText(f"Origem selecionada: {devices[0]}" if devices else "Origem selecionada: nenhum scanner")
        if devices: self.device_changed.emit(devices[0])

    def set_sources(self, sources: list[tuple[str, str]]) -> None:
        self.source_combo.clear()
        if not sources:
            self.source_combo.addItem("Fonte automática", None); self.source_combo.setEnabled(False)
        else:
            for label, value in sources: self.source_combo.addItem(label, value)
            self.source_combo.setEnabled(len(sources) > 1)
        self._update_capabilities()

    def get_scan_config(self) -> dict:
        return {
            "device": self.device_combo.currentText() if self.device_combo.isEnabled() else "",
            "dpi": int(self.dpi_combo.currentData()),
            "color": str(self.color_combo.currentData()),
            "source": self.source_combo.currentData(),
        }

    def set_pages(self, pages: list[tuple[str, QPixmap]], current: int) -> None:
        self._building_pages = True; self.page_list.blockSignals(True); self.page_list.clear()
        self._pixmaps = dict(pages)
        for index, (page_id, pixmap) in enumerate(pages):
            item = QListWidgetItem(str(index + 1)); item.setData(Qt.ItemDataRole.UserRole, page_id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setIcon(QIcon(pixmap.scaled(115, 145, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            self.page_list.addItem(item)
        self.page_list.blockSignals(False); self._building_pages = False
        if pages: self.page_list.setCurrentRow(min(max(current, 0), len(pages) - 1))
        else: self.preview.set_pixmap(QPixmap()); self.page_indicator.setText("0 / 0")

    def set_document_state(self, name: str, count: int, busy: bool) -> None:
        self.document_label.setText(f"Documento: {name}"); self.count_label.setText(f"Páginas: {count}")
        self.pages_heading.setText(f"PÁGINAS ({count})")
        for button in self.document_actions + [self.btn_save, self.btn_ged]: button.setEnabled(count > 0 and not busy)
        for button in (self.btn_import_top, self.btn_open_top, self.btn_add_top, self.btn_scan, self.btn_scan_top, self.btn_refresh): button.setEnabled(not busy and (button not in (self.btn_scan, self.btn_scan_top) or self.device_combo.isEnabled()))
        self.btn_scan.setText("Digitalizando..." if busy else "Iniciar Digitalização")

    def set_status(self, message: str) -> None:
        self.setToolTip(message)

    def selected_indexes(self) -> list[int]:
        return sorted({self.page_list.row(item) for item in self.page_list.selectedItems()})

    def ordered_ids(self) -> list[str]:
        return [str(self.page_list.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.page_list.count())]

    def _current_changed(self, index: int) -> None:
        if self._building_pages: return
        if 0 <= index < self.page_list.count():
            page_id = str(self.page_list.item(index).data(Qt.ItemDataRole.UserRole))
            self.preview.set_pixmap(self._pixmaps.get(page_id, QPixmap()))
            self.page_indicator.setText(f"{index + 1} / {self.page_list.count()}")
            self.current_page_changed.emit(index)

    def _rows_moved(self) -> None:
        if not self._building_pages: self.reorder_requested.emit(self.ordered_ids())

    def _move(self, delta: int) -> None:
        row = self.page_list.currentRow(); target = row + delta
        if row < 0 or not 0 <= target < self.page_list.count(): return
        ids = self.ordered_ids(); ids[row], ids[target] = ids[target], ids[row]
        self.reorder_requested.emit(ids)

    def _step(self, delta: int) -> None:
        if self.page_list.count(): self.page_list.setCurrentRow(min(max(self.page_list.currentRow() + delta, 0), self.page_list.count() - 1))

    def _request_remove(self) -> None:
        indexes = self.selected_indexes()
        if indexes: self.remove_requested.emit(indexes)

    def _request_rotate(self, degrees: int) -> None:
        indexes = self.selected_indexes()
        if not indexes and self.page_list.currentRow() >= 0: indexes = [self.page_list.currentRow()]
        if indexes: self.rotate_requested.emit(indexes, degrees)

    def _request_extract(self) -> None:
        indexes = self.selected_indexes()
        if not indexes: return
        path, _ = QFileDialog.getSaveFileName(self, "Extrair páginas", "paginas_extraidas.pdf", "PDF (*.pdf)")
        if path: self.extract_requested.emit(indexes, path)

    def _choose_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Importar imagens", "", "Imagens (*.jpg *.jpeg *.png *.bmp *.tif *.tiff)")
        if paths: self.import_images_requested.emit(paths)

    def _choose_open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if path: self.open_pdf_requested.emit(path)

    def _choose_add_pdfs(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Adicionar PDFs", "", "PDF (*.pdf)")
        if paths: self.add_pdfs_requested.emit(paths)

    def _choose_save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Salvar PDF", "documento.pdf", "PDF (*.pdf)")
        if path: self.save_requested.emit(path)

    def _choose_split_directory(self) -> None:
        if not self.page_list.count():
            return
        directory = QFileDialog.getExistingDirectory(self, "Pasta para páginas divididas")
        if directory:
            self.split_requested.emit(directory)

    def _device_selected(self, value: str) -> None:
        self.origin_label.setText(f"Origem selecionada: {value}")
        if self.device_combo.isEnabled(): self.device_changed.emit(value)

    def _update_capabilities(self) -> None:
        value = str(self.source_combo.currentData() or "").lower()
        adf = any(term in value for term in ("adf", "feeder", "duplex"))
        duplex = "duplex" in value
        self.adf.setVisible(adf); self.adf.setChecked(adf)
        self.duplex.setVisible(duplex); self.duplex.setChecked(duplex)

    def _connect_shortcuts(self) -> None:
        QShortcut(QKeySequence.StandardKey.Delete, self, activated=self._request_remove)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._choose_save)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self._choose_open_pdf)

    @staticmethod
    def _heading(text: str) -> QLabel:
        label = QLabel(text); label.setObjectName("capturePdfSection"); return label

    @staticmethod
    def _combo() -> QComboBox:
        combo = QComboBox(); combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed); return combo

    @staticmethod
    def _menu_action(menu: QMenu, text: str, icon: str, callback) -> QAction:
        action = menu.addAction(IconProvider.icon(icon), text); action.triggered.connect(callback); return action

    @staticmethod
    def _toolbar_button(text: str, icon: str, callback) -> QToolButton:
        button = QToolButton(); button.setObjectName("capturePdfToolbarButton"); button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); button.setIcon(IconProvider.icon(icon)); button.setIconSize(QSize(24, 24)); button.clicked.connect(callback); return button

    @staticmethod
    def _wide_button(text: str, icon: str, callback) -> QPushButton:
        button = QPushButton(text); button.setObjectName("capturePdfWideButton"); IconProvider.apply(button, icon); button.clicked.connect(callback); return button

    @staticmethod
    def _compact_action(text: str, icon: str, callback) -> QPushButton:
        button = QPushButton(text); button.setObjectName("capturePdfAction"); button.setToolTip(text); IconProvider.apply(button, icon); button.clicked.connect(callback); return button

    @staticmethod
    def _nav(text: str, icon: str, callback) -> QPushButton:
        button = QPushButton(); button.setFixedSize(34, 32); button.setToolTip(text); IconProvider.apply(button, icon); button.clicked.connect(callback); return button
