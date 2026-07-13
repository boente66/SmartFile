from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSize, Qt, pyqtSignal as Signal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QFrame, QHBoxLayout, QLabel, QListView,
    QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSplitter,
    QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider
from app.views.widgets.preview_widget import PreviewWidget


class PDFView(QWidget):
    """Interface do PDF Tools; coleta ações sem executar manipulação estrutural."""

    open_pdf_requested = Signal(str)
    add_files_requested = Signal(list)
    remove_pages_requested = Signal(list)
    reorder_pages_requested = Signal(list)
    rotate_pages_requested = Signal(list)
    extract_pages_requested = Signal(list, str)
    split_pdf_requested = Signal(str)
    merge_pdfs_requested = Signal(list, str)
    save_pdf_requested = Signal()
    back_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("pdfTools")
        self._input_pdf: str | None = None
        self._pixmaps: list[QPixmap] = []
        self._page_ids: list[int] = []
        self._setup_ui()
        self.set_document_loaded(False)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_toolbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("pdfToolsSplitter")
        splitter.addWidget(self._build_pages_panel())
        splitter.addWidget(self._build_preview_panel())
        splitter.addWidget(self._build_actions_panel())
        splitter.setSizes([280, 760, 300])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(2, True)
        self.splitter = splitter
        root.addWidget(splitter, 1)

        status = QHBoxLayout()
        status.setContentsMargins(14, 8, 14, 8)
        self.file_status = QLabel("Nenhum PDF carregado")
        self.size_status = QLabel("—")
        status.addWidget(self.file_status)
        status.addStretch()
        status.addWidget(self.size_status)
        status_widget = QWidget(); status_widget.setObjectName("pdfToolsStatus")
        status_widget.setLayout(status)
        root.addWidget(status_widget)

    def _build_toolbar(self) -> QWidget:
        toolbar = QWidget(); toolbar.setObjectName("pdfToolsToolbar")
        layout = QHBoxLayout(toolbar); layout.setContentsMargins(12, 6, 12, 6); layout.setSpacing(5)
        self.toolbar_buttons = []
        specs = (
            ("Voltar", "pdf_back", self.back_requested.emit),
            ("Adicionar", "pdf_add", self._choose_add_files),
            ("Remover", "pdf_remove", self._request_remove),
            ("Mover", "pdf_move", lambda: self.page_list.setFocus()),
            ("Girar", "pdf_rotate", self._request_rotate),
            ("Extrair", "pdf_extract", self._request_extract),
            ("Dividir", "pdf_split", self._request_split),
            ("Mesclar", "pdf_merge", self._request_merge),
            ("Salvar", "pdf_save", self._request_save),
        )
        for text, icon, callback in specs:
            button = self._action_button(text, icon)
            button.clicked.connect(callback)
            layout.addWidget(button)
            self.toolbar_buttons.append(button)
        layout.addStretch()
        self.btn_visualize = self._action_button("Visualizar", "visualize")
        self.btn_visualize.setChecked(True); self.btn_visualize.setCheckable(True)
        self.btn_edit = self._action_button("Editar", "edit"); self.btn_edit.setCheckable(True)
        self.btn_visualize.clicked.connect(lambda: self._set_mode(False))
        self.btn_edit.clicked.connect(lambda: self._set_mode(True))
        layout.addWidget(self.btn_visualize); layout.addWidget(self.btn_edit)
        return toolbar

    def _build_pages_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("pdfToolsPanel")
        layout = QVBoxLayout(panel); layout.setContentsMargins(10, 10, 10, 10)
        self.pages_heading = QLabel("PÁGINAS")
        layout.addWidget(self.pages_heading)
        self.page_list = QListWidget()
        self.page_list.setViewMode(QListView.ViewMode.IconMode)
        self.page_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.page_list.setMovement(QListView.Movement.Snap)
        self.page_list.setIconSize(QSize(120, 160))
        self.page_list.setGridSize(QSize(142, 195))
        self.page_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.page_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.page_list.currentRowChanged.connect(self._on_page_selected)
        self.page_list.model().rowsMoved.connect(self._emit_reorder)
        layout.addWidget(self.page_list, 1)
        self.pages_count = QLabel("0 páginas")
        layout.addWidget(self.pages_count)
        return panel

    def _build_preview_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("pdfToolsPreviewPanel")
        layout = QVBoxLayout(panel); layout.setContentsMargins(10, 8, 10, 8)
        navigation = QHBoxLayout()
        self.btn_previous = self._small_button("Página anterior", "viewer_previous_page")
        self.page_indicator = QLabel("0 / 0")
        self.btn_next = self._small_button("Próxima página", "viewer_next_page")
        self.btn_previous.clicked.connect(lambda: self._step_page(-1))
        self.btn_next.clicked.connect(lambda: self._step_page(1))
        navigation.addStretch(); navigation.addWidget(self.btn_previous)
        navigation.addWidget(self.page_indicator); navigation.addWidget(self.btn_next); navigation.addStretch()
        layout.addLayout(navigation)
        self.preview = PreviewWidget(); self.preview.setObjectName("pdfToolsPreview")
        layout.addWidget(self.preview, 1)
        return panel

    def _build_actions_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("pdfToolsActions")
        layout = QVBoxLayout(panel); layout.setContentsMargins(12, 12, 12, 12); layout.setSpacing(6)
        heading = QLabel("AÇÕES"); heading.setObjectName("pdfToolsSectionTitle"); layout.addWidget(heading)
        actions = (
            ("Adicionar arquivos", "Adiciona PDFs ao documento", "pdf_add", self._choose_add_files),
            ("Remover páginas", "Remove as páginas selecionadas", "pdf_remove", self._request_remove),
            ("Mover páginas", "Arraste as miniaturas para ordenar", "pdf_move", lambda: self.page_list.setFocus()),
            ("Girar páginas", "Gira as páginas selecionadas", "pdf_rotate", self._request_rotate),
            ("Extrair páginas", "Cria um PDF com a seleção", "pdf_extract", self._request_extract),
            ("Dividir PDF", "Cria um arquivo para cada página", "pdf_split", self._request_split),
            ("Mesclar PDF", "Combina vários PDFs em um só", "pdf_merge", self._request_merge),
        )
        self.action_buttons = []
        for title, description, icon, callback in actions:
            button = QPushButton(f"{title}\n{description}")
            button.setObjectName("pdfToolsActionButton")
            button.setToolTip(description)
            IconProvider.apply(button, icon, QSize(28, 28))
            button.clicked.connect(callback)
            layout.addWidget(button)
            self.action_buttons.append(button)
        info_title = QLabel("INFORMAÇÕES"); info_title.setObjectName("pdfToolsSectionTitle")
        layout.addWidget(info_title)
        self.info_name = QLabel("Nome: —"); self.info_pages = QLabel("Páginas: —"); self.info_size = QLabel("Tamanho: —")
        for label in (self.info_name, self.info_pages, self.info_size):
            label.setWordWrap(True); layout.addWidget(label)
        layout.addStretch()
        self.btn_apply_save = QPushButton("Aplicar e Salvar")
        self.btn_apply_save.setObjectName("pdfToolsSave")
        IconProvider.apply(self.btn_apply_save, "pdf_save")
        self.btn_apply_save.clicked.connect(self._request_save)
        layout.addWidget(self.btn_apply_save)
        return panel

    def load_pdf(self, path: str) -> None:
        self._input_pdf = path
        self.page_list.clear(); self._pixmaps.clear(); self._page_ids.clear()
        self.preview.set_pixmap(QPixmap())
        file_path = Path(path)
        size = file_path.stat().st_size if file_path.is_file() else 0
        self.file_status.setText(f"Arquivo: {file_path.name}")
        self.size_status.setText(f"Tamanho: {self._format_size(size)}")
        self.info_name.setText(f"Nome: {file_path.name}")
        self.info_size.setText(f"Tamanho: {self._format_size(size)}")
        self.set_document_loaded(True)

    def show_thumbnails(self, pixmaps: list[QPixmap], page_ids: list[int] | None = None) -> None:
        self._pixmaps = pixmaps
        self._page_ids = list(page_ids) if page_ids is not None else list(range(len(pixmaps)))
        self.page_list.clear()
        for index, (pixmap, page_id) in enumerate(zip(pixmaps, self._page_ids)):
            item = QListWidgetItem(f"Página {index + 1}")
            item.setData(Qt.ItemDataRole.UserRole, page_id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setIcon(QIcon(pixmap.scaled(120, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))
            self.page_list.addItem(item)
        count = len(pixmaps)
        self.pages_count.setText(f"{count} página(s)")
        self.info_pages.setText(f"Páginas: {count}")
        if pixmaps:
            self.page_list.setCurrentRow(0)
        else:
            self.page_indicator.setText("0 / 0")

    def selected_page_ids(self) -> list[int]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.page_list.selectedItems()]

    def set_document_loaded(self, loaded: bool) -> None:
        for button in self.toolbar_buttons[2:] + self.action_buttons:
            button.setEnabled(loaded)
        self.btn_apply_save.setEnabled(loaded)

    def _open_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF", "", "PDF (*.pdf)")
        if path: self.open_pdf_requested.emit(path)

    def _choose_add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Adicionar PDFs", "", "PDF (*.pdf)")
        if paths: self.add_files_requested.emit(paths)

    def _request_remove(self) -> None:
        pages = self._require_selection()
        if pages: self.remove_pages_requested.emit(pages)

    def _request_rotate(self) -> None:
        pages = self._require_selection()
        if pages: self.rotate_pages_requested.emit(pages)

    def _request_extract(self) -> None:
        pages = self._require_selection()
        if not pages: return
        path, _ = QFileDialog.getSaveFileName(self, "Extrair páginas", "paginas_extraidas.pdf", "PDF (*.pdf)")
        if path: self.extract_pages_requested.emit(pages, path)

    def _request_split(self) -> None:
        if not self._input_pdf: return
        directory = QFileDialog.getExistingDirectory(self, "Pasta para páginas divididas")
        if directory: self.split_pdf_requested.emit(directory)

    def _request_merge(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "PDFs para mesclar", "", "PDF (*.pdf)")
        if not paths: return
        output, _ = QFileDialog.getSaveFileName(self, "Salvar PDF mesclado", "mesclado.pdf", "PDF (*.pdf)")
        if output: self.merge_pdfs_requested.emit(paths, output)

    def _request_save(self) -> None:
        if self._input_pdf: self.save_pdf_requested.emit()

    def _require_selection(self) -> list[int]:
        if not self._input_pdf:
            QMessageBox.warning(self, "PDF Tools", "Nenhum PDF carregado."); return []
        pages = self.selected_page_ids()
        if not pages:
            QMessageBox.warning(self, "PDF Tools", "Selecione ao menos uma página.")
        return pages

    def _emit_reorder(self) -> None:
        self.reorder_pages_requested.emit([
            self.page_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.page_list.count())
        ])

    def _on_page_selected(self, index: int) -> None:
        if 0 <= index < len(self._pixmaps):
            self.preview.set_pixmap(self._pixmaps[index])
            self.page_indicator.setText(f"{index + 1} / {len(self._pixmaps)}")

    def _step_page(self, delta: int) -> None:
        if self.page_list.count():
            self.page_list.setCurrentRow(min(max(self.page_list.currentRow() + delta, 0), self.page_list.count() - 1))

    def _set_mode(self, editing: bool) -> None:
        self.btn_edit.setChecked(editing); self.btn_visualize.setChecked(not editing)

    @staticmethod
    def _action_button(text: str, icon: str) -> QPushButton:
        button = QPushButton(text); button.setObjectName("pdfToolsToolbarButton")
        button.setToolTip(text); IconProvider.apply(button, icon, QSize(22, 22)); return button

    @staticmethod
    def _small_button(text: str, icon: str) -> QPushButton:
        button = QPushButton(); button.setFixedSize(34, 34); button.setToolTip(text); IconProvider.apply(button, icon); return button

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB": return f"{value:.1f} {unit}"
            value /= 1024
        return "—"
