from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)

from app.models.pdf_document_info import PDFDocumentInfo
from app.ui.icon_provider import IconProvider
from app.views.widgets.pdf_info_panel import PDFInfoPanel
from app.views.widgets.pdf_search_bar import PDFSearchBar
from app.views.widgets.pdf_thumbnail_panel import PDFThumbnailPanel
from app.views.widgets.preview_widget import PreviewWidget


class PDFViewerView(QWidget):
    back_requested = pyqtSignal()
    open_requested = pyqtSignal(str)
    page_requested = pyqtSignal(int)
    first_requested = pyqtSignal()
    previous_requested = pyqtSignal()
    next_requested = pyqtSignal()
    last_requested = pyqtSignal()
    zoom_requested = pyqtSignal(float)
    fit_width_requested = pyqtSignal()
    fit_page_requested = pyqtSignal()
    rotate_left_requested = pyqtSignal()
    rotate_right_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    search_previous_requested = pyqtSignal()
    search_next_requested = pyqtSignal()
    print_requested = pyqtSignal()
    fullscreen_requested = pyqtSignal()
    escape_requested = pyqtSignal()
    sign_requested = pyqtSignal()
    handwritten_sign_requested = pyqtSignal()
    validate_signatures_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("pdfViewer")
        self._page_count = 0
        self._current_zoom = 1.0
        self._compact_toolbar: bool | None = None
        self._setup_ui()
        self._setup_shortcuts()
        self.set_document_loaded(False)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.toolbar = self._build_toolbar()
        root.addWidget(self.toolbar)
        self.search_bar = PDFSearchBar()
        self.search_bar.search_requested.connect(self.search_requested.emit)
        self.search_bar.previous_requested.connect(self.search_previous_requested.emit)
        self.search_bar.next_requested.connect(self.search_next_requested.emit)
        self.search_bar.close_requested.connect(self.search_bar.hide)
        root.addWidget(self.search_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter = splitter
        self.thumbnails = PDFThumbnailPanel()
        self.thumbnails.setObjectName("pdfThumbnailPanel")
        self.thumbnails.page_selected.connect(self.page_requested.emit)
        splitter.addWidget(self.thumbnails)
        self.preview = PreviewWidget()
        self.preview.setObjectName("pdfViewerPreview")
        splitter.addWidget(self.preview)
        tabs = QTabWidget()
        self.side_tabs = tabs
        tabs.setObjectName("pdfViewerTabs")
        self.info_panel = PDFInfoPanel()
        tabs.addTab(self.info_panel, "Informações")
        self.signature_label = QLabel("A validação de assinaturas será exibida aqui.")
        self.signature_label.setWordWrap(True)
        tabs.addTab(self.signature_label, "Assinaturas")
        splitter.addWidget(tabs)
        splitter.setSizes([210, 850, 300])
        root.addWidget(splitter, 1)

        status = QHBoxLayout()
        self.loading_label = QLabel("Pronto")
        self.page_status = QLabel("Página 0 de 0")
        self.page_size_status = QLabel("—")
        self.zoom_status = QLabel("Zoom: 100%")
        self.signature_status = QLabel("Sem assinaturas detectadas")
        status.addWidget(self.loading_label)
        status.addStretch()
        for label in (self.page_status, self.page_size_status, self.zoom_status, self.signature_status):
            status.addWidget(label)
        self.status_bar = QWidget()
        self.status_bar.setObjectName("pdfViewerStatus")
        self.status_bar.setLayout(status)
        root.addWidget(self.status_bar)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget()
        toolbar.setObjectName("pdfViewerToolbar")
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)
        self.toolbar_layout = layout
        self.buttons = []

        def button(text, callback, icon=None):
            widget = QPushButton(text)
            if icon:
                IconProvider.apply(widget, icon)
            widget.setProperty("actionText", text)
            widget.setAccessibleName(text)
            widget.setToolTip(text)
            widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            widget.clicked.connect(callback)
            layout.addWidget(widget)
            self.buttons.append(widget)
            return widget

        self.btn_back = button(
            "Voltar para Documentos", self.back_requested.emit, "pdf_back"
        )
        self.btn_open = button("Abrir", self._choose_pdf, "viewer_open")
        layout.addSpacing(10)
        button("Imprimir", self.print_requested.emit, "viewer_print")
        button("Pesquisar", self.search_bar_open, "viewer_search")
        layout.addSpacing(10)
        button("Primeira", self.first_requested.emit, "viewer_first_page")
        button("Anterior", self.previous_requested.emit, "viewer_previous_page")
        self.page_edit = QLineEdit("1")
        self.page_edit.setFixedWidth(52)
        self.page_edit.returnPressed.connect(self._request_page)
        self.total_label = QLabel("/ 0")
        layout.addWidget(self.page_edit)
        layout.addWidget(self.total_label)
        button("Próxima", self.next_requested.emit, "viewer_next_page")
        button("Última", self.last_requested.emit, "viewer_last_page")
        layout.addSpacing(10)
        button("Diminuir zoom", lambda: self._step_zoom(-0.25), "viewer_zoom_out")
        self.zoom_combo = QComboBox()
        for percent in (50, 75, 100, 125, 150, 200):
            self.zoom_combo.addItem(f"{percent}%", percent / 100)
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.setFixedWidth(82)
        self.zoom_combo.currentIndexChanged.connect(
            lambda: self.zoom_requested.emit(float(self.zoom_combo.currentData()))
        )
        layout.addWidget(self.zoom_combo)
        button("Aumentar zoom", lambda: self._step_zoom(0.25), "viewer_zoom_in")
        button("Ajustar largura", self.fit_width_requested.emit, "viewer_fit_width")
        button("Ajustar página", self.fit_page_requested.emit, "viewer_fit_page")
        button("Girar esq.", self.rotate_left_requested.emit, "viewer_rotate_left")
        button("Girar dir.", self.rotate_right_requested.emit, "viewer_rotate_right")
        self.btn_sign = button("Assinar digitalmente", self.sign_requested.emit, "viewer_sign")
        self.btn_handwritten_sign = button(
            "Assinatura manuscrita",
            self.handwritten_sign_requested.emit,
            "viewer_handwritten_sign",
        )
        self.btn_validate = button(
            "Validar assinaturas", self.validate_signatures_requested.emit, "viewer_validate"
        )
        layout.addStretch()
        self._set_toolbar_compact(True)
        return toolbar

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._set_toolbar_compact(event.size().width() < 1500)

    def _set_toolbar_compact(self, compact: bool) -> None:
        if compact == self._compact_toolbar:
            return
        self._compact_toolbar = compact
        self.toolbar_layout.setSpacing(3 if compact else 6)
        for widget in self.buttons:
            action_text = str(widget.property("actionText"))
            if compact:
                widget.setText("")
                widget.setFixedSize(38, 38)
            else:
                widget.setText(action_text)
                widget.setMinimumSize(0, 0)
                widget.setMaximumSize(16777215, 38)
        self.page_edit.setFixedWidth(46 if compact else 52)
        self.zoom_combo.setFixedWidth(74 if compact else 82)

    def _setup_shortcuts(self) -> None:
        bindings = (
            ("Ctrl+F", self.search_bar_open), ("PageUp", self.previous_requested.emit),
            ("PageDown", self.next_requested.emit), ("Home", self.first_requested.emit),
            ("End", self.last_requested.emit), ("Ctrl++", lambda: self._step_zoom(0.25)),
            ("Ctrl+-", lambda: self._step_zoom(-0.25)), ("Ctrl+0", lambda: self.zoom_requested.emit(1.0)),
            ("F11", self.fullscreen_requested.emit),
            ("Esc", self._escape),
        )
        self._shortcuts = []
        for sequence, callback in bindings:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def set_document(self, info: PDFDocumentInfo) -> None:
        self._page_count = info.page_count
        self.total_label.setText(f"/ {info.page_count}")
        self.thumbnails.prepare(info.page_count)
        self.info_panel.set_info(info)
        self.page_size_status.setText(f"{info.page_width / 72 * 2.54:.1f} × {info.page_height / 72 * 2.54:.1f} cm")
        self.signature_status.setText(
            f"{info.signature_count} assinatura(s)" if info.has_signatures else "Sem assinaturas detectadas"
        )
        self.set_document_loaded(True)

    def set_rendered_page(self, page_number: int, page_count: int, pixmap: QPixmap, zoom: float) -> None:
        self._current_zoom = zoom
        self.preview.set_pixmap(pixmap)
        self.page_edit.setText(str(page_number))
        self.page_status.setText(f"Página {page_number} de {page_count}")
        self.zoom_status.setText(f"Zoom: {zoom * 100:.0f}%")
        self.thumbnails.select_page(page_number)
        self.set_loading(False)

    def set_thumbnail(self, page_number: int, image) -> None:
        self.thumbnails.set_thumbnail(page_number, image)

    def set_loading(self, loading: bool, message: str = "Carregando…") -> None:
        self.loading_label.setText(message if loading else "Pronto")

    def set_document_loaded(self, loaded: bool) -> None:
        always_enabled = {self.btn_back, self.btn_open}
        for button in self.buttons:
            button.setEnabled(loaded or button in always_enabled)
        self.page_edit.setEnabled(loaded)
        self.zoom_combo.setEnabled(loaded)
        self.btn_sign.setEnabled(loaded)
        self.btn_handwritten_sign.setEnabled(loaded)
        self.btn_validate.setEnabled(loaded)

    def update_search_count(self, current: int, total: int) -> None:
        self.search_bar.set_count(current, total)

    def search_bar_open(self) -> None:
        self.search_bar.open()

    def _escape(self) -> None:
        if self.search_bar.isVisible():
            self.search_bar.hide()
        else:
            self.escape_requested.emit()

    def available_preview_size(self) -> QSize:
        return self.preview.scroll.viewport().size()

    def set_presentation_mode(self, enabled: bool) -> None:
        self.toolbar.setVisible(not enabled)
        self.search_bar.setVisible(False if enabled else self.search_bar.isVisible())
        self.thumbnails.setVisible(not enabled)
        self.side_tabs.setVisible(not enabled)
        self.status_bar.setVisible(not enabled)

    def _choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if path:
            self.open_requested.emit(path)

    def _request_page(self) -> None:
        try:
            self.page_requested.emit(int(self.page_edit.text()))
        except ValueError:
            self.page_edit.setText("1")

    def _step_zoom(self, delta: float) -> None:
        self.zoom_requested.emit(self._current_zoom + delta)
