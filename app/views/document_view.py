from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from app.models.document_model import DocumentModel


class DocumentView(QWidget):
    import_requested = Signal()
    search_requested = Signal(str)
    filter_requested = Signal(str)
    refresh_requested = Signal()
    open_requested = Signal(int)
    convert_requested = Signal(int)
    pdf_tools_requested = Signal(int)
    delete_requested = Signal(int)
    favorite_requested = Signal(int)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Mini GED local")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        intro = QLabel(
            "Importe documentos, consulte o histórico e acesse arquivos locais sem depender de rede ou nuvem."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por nome, categoria ou tags")
        self.search_edit.textChanged.connect(self._emit_search)
        controls.addWidget(QLabel("Buscar"))
        controls.addWidget(self.search_edit, 1)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Todos", "PDF", "DOC", "SPREADSHEET", "IMAGE", "TEXT", "OTHER"])
        self.type_combo.currentTextChanged.connect(self._emit_filter)
        controls.addWidget(QLabel("Tipo"))
        controls.addWidget(self.type_combo)
        layout.addLayout(controls)

        actions = QHBoxLayout()
        self.btn_import = QPushButton("Importar")
        self.btn_import.clicked.connect(self.import_requested.emit)
        self.btn_open = QPushButton("Abrir")
        self.btn_open.clicked.connect(self._emit_open)
        self.btn_convert = QPushButton("Converter")
        self.btn_convert.clicked.connect(self._emit_convert)
        self.btn_pdf = QPushButton("PDF Tools")
        self.btn_pdf.clicked.connect(self._emit_pdf_tools)
        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.clicked.connect(self._emit_delete)
        self.btn_favorite = QPushButton("Favorito")
        self.btn_favorite.clicked.connect(self._emit_favorite)

        actions.addWidget(self.btn_import)
        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_convert)
        actions.addWidget(self.btn_pdf)
        actions.addWidget(self.btn_delete)
        actions.addWidget(self.btn_favorite)
        layout.addLayout(actions)

        self.status_label = QLabel("Nenhum documento importado")
        layout.addWidget(self.status_label)

        self.documents_table = QTableWidget(0, 5)
        self.documents_table.setHorizontalHeaderLabels(["Nome", "Tipo", "Categoria", "Tamanho", "Favorito"])
        self.documents_table.setAlternatingRowColors(True)
        self.documents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.documents_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.documents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.documents_table, 1)

    def set_documents(self, documents: list[DocumentModel]):
        self.documents_table.setRowCount(len(documents))
        for row_index, document in enumerate(documents):
            self.documents_table.setItem(row_index, 0, QTableWidgetItem(document.name))
            self.documents_table.setItem(row_index, 1, QTableWidgetItem(document.file_type or ""))
            self.documents_table.setItem(row_index, 2, QTableWidgetItem(document.category or ""))
            self.documents_table.setItem(row_index, 3, QTableWidgetItem(self._format_size(document.size)))
            self.documents_table.setItem(row_index, 4, QTableWidgetItem("★" if document.favorite else ""))

            for column in range(self.documents_table.columnCount()):
                self.documents_table.item(row_index, column).setData(Qt.ItemDataRole.UserRole, document.id)

        self.documents_table.resizeColumnsToContents()

    def set_status(self, text: str):
        self.status_label.setText(text)

    def current_search(self) -> str:
        return self.search_edit.text().strip()

    def current_type_filter(self) -> str:
        return self.type_combo.currentText()

    def selected_document_id(self) -> int | None:
        selected = self.documents_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        item = self.documents_table.item(row, 0)
        if item is None:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole) or 0) or None

    def _emit_search(self, text: str):
        self.search_requested.emit(text)

    def _emit_filter(self, value: str):
        self.filter_requested.emit(value)

    def _emit_open(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.open_requested.emit(document_id)

    def _emit_convert(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.convert_requested.emit(document_id)

    def _emit_pdf_tools(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.pdf_tools_requested.emit(document_id)

    def _emit_delete(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.delete_requested.emit(document_id)

    def _emit_favorite(self):
        document_id = self.selected_document_id()
        if document_id is not None:
            self.favorite_requested.emit(document_id)

    def _format_size(self, size: int | None) -> str:
        if size is None:
            return ""
        units = ["B", "KB", "MB", "GB"]
        value = float(size)
        for unit in units:
            if value < 1024 or unit == units[-1]:
                return f"{value:.0f} {unit}"
            value /= 1024
        return f"{value:.0f} GB"
