from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QAbstractItemView,
    QPushButton, QFileDialog, QMessageBox
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal as Signal, QSize

from app.views.widgets.preview_widget import PreviewWidget


class PDFView(QWidget):
    """
    PDFView com preview de páginas e drag & drop.
    View pura: NÃO salva, NÃO edita arquivo.
    """

    open_pdf_requested = Signal(str)
    remove_pages_requested = Signal(list)
    reorder_pages_requested = Signal(list)
    save_pdf_requested = Signal()

    def __init__(self):
        super().__init__()

        self._input_pdf: str | None = None
        self._pixmaps: list[QPixmap] = []

        self._setup_ui()

    # -------------------------
    # UI
    # -------------------------
    def _setup_ui(self):

        main_layout = QHBoxLayout(self)

        self.page_list = QListWidget()
        self.page_list.setIconSize(QSize(120, 160))
        self.page_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.page_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

        self.page_list.currentRowChanged.connect(self._on_page_selected)

        # 🔴 Detecta mudança de ordem
        self.page_list.model().rowsMoved.connect(self._emit_reorder)

        self.preview = PreviewWidget()

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.page_list)

        btn_layout = QHBoxLayout()

        btn_add = QPushButton("Abrir PDF")
        btn_add.clicked.connect(self._open_pdf)

        btn_remove = QPushButton("Excluir páginas")
        btn_remove.clicked.connect(self._request_remove)

        btn_save = QPushButton("Salvar PDF")
        btn_save.clicked.connect(self._request_save)

        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addWidget(btn_save)

        left_layout.addLayout(btn_layout)

        main_layout.addLayout(left_layout, 1)
        main_layout.addWidget(self.preview, 2)

    # -------------------------
    # API pública
    # -------------------------
    def load_pdf(self, path: str):

        self._input_pdf = path
        self.page_list.clear()
        self._pixmaps.clear()
        self.preview.set_pixmap(QPixmap())

    # -------------------------
    # Actions
    # -------------------------
    def _open_pdf(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if path:
            self.open_pdf_requested.emit(path)

    def _request_remove(self):

        if not self._input_pdf:
            QMessageBox.warning(self, "Aviso", "Nenhum PDF carregado.")
            return

        selected = self.page_list.selectedItems()

        if not selected:
            QMessageBox.warning(self, "Aviso", "Selecione páginas.")
            return

        pages = [item.data(Qt.UserRole) for item in selected]

        self.remove_pages_requested.emit(pages)

    def _request_save(self):

        if not self._input_pdf:
            QMessageBox.warning(self, "Aviso", "Nenhum PDF carregado.")
            return

        self.save_pdf_requested.emit()

    # -------------------------
    # Reordenar páginas
    # -------------------------
    def _emit_reorder(self):

        order = []

        for i in range(self.page_list.count()):
            item = self.page_list.item(i)
            order.append(item.data(Qt.UserRole))

        self.reorder_pages_requested.emit(order)

    # -------------------------
    # Preview
    # -------------------------
    def show_thumbnails(self, pixmaps: list[QPixmap]):

        self._pixmaps = pixmaps
        self.page_list.clear()

        for i, pixmap in enumerate(pixmaps):

            item = QListWidgetItem(f"Página {i + 1}")
            item.setData(Qt.UserRole, i)

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

        if pixmaps:
            self.preview.set_pixmap(pixmaps[0])

    def _on_page_selected(self, index: int):

        if 0 <= index < len(self._pixmaps):
            self.preview.set_pixmap(self._pixmaps[index])
