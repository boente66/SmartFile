from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
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
)

from app.models.document_model import DocumentModel
from app.ui.icon_provider import IconProvider
from app.views.widgets.document_details_widget import DocumentDetailsWidget


class DocumentView(QWidget):
    import_requested = pyqtSignal()
    search_requested = pyqtSignal(str)
    filter_requested = pyqtSignal(str)
    refresh_requested = pyqtSignal()
    document_selected = pyqtSignal(int)
    open_requested = pyqtSignal(int)
    convert_requested = pyqtSignal(int)
    pdf_tools_requested = pyqtSignal(int)
    delete_requested = pyqtSignal(int)
    favorite_requested = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        # main two-column layout: list (left) + detail panel (right)
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(12)

        # Left column: header, controls, actions, table
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(10)

        title = QLabel("Documentos")
        title.setObjectName("title")
        left_layout.addWidget(title)

        intro = QLabel(
            "Central de documentos do SmartFile"
        )
        intro.setWordWrap(True)
        left_layout.addWidget(intro)

        controls = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por nome, categoria ou tags")
        self.search_edit.textChanged.connect(self._emit_search)
        controls.addWidget(QLabel("Buscar"))
        controls.addWidget(self.search_edit, 1)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["Todos", "PDF", "DOCX", "SPREADSHEET", "IMAGE", "TEXT", "OTHER"])
        self.type_combo.currentTextChanged.connect(self._emit_filter)
        controls.addWidget(QLabel("Tipo"))
        controls.addWidget(self.type_combo)
        self.btn_import = QPushButton("Adicionar documento")
        self.btn_import.setObjectName("primary")
        IconProvider.apply(self.btn_import, "import")
        self.btn_import.clicked.connect(self.import_requested.emit)
        controls.addWidget(self.btn_import)
        left_layout.addLayout(controls)

        self.status_label = QLabel("Nenhum documento importado")
        self.status_label.setObjectName("documentCount")
        left_layout.addWidget(self.status_label)

        self.documents_table = QTableWidget(0, 5)
        self.documents_table.setHorizontalHeaderLabels(["Nome", "Tipo", "Categoria", "Tamanho", "Favorito"])
        self.documents_table.setAlternatingRowColors(True)
        self.documents_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.documents_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.documents_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.documents_table.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.documents_table, 1)

        self.details = DocumentDetailsWidget()
        self.details.open_requested.connect(self.open_requested.emit)
        self.details.convert_requested.connect(self.convert_requested.emit)
        self.details.pdf_tools_requested.connect(self.pdf_tools_requested.emit)
        self.details.trash_requested.connect(self.delete_requested.emit)
        self.details.favorite_requested.connect(self.favorite_requested.emit)

        # Compatibilidade para consumidores que referenciam as ações públicas.
        self.btn_open = self.details.btn_open
        self.btn_convert = self.details.btn_convert
        self.btn_pdf = self.details.btn_pdf
        self.btn_delete = self.details.btn_trash
        self.btn_favorite = self.details.btn_favorite

        # assemble
        main_layout.addWidget(left, 3)
        main_layout.addWidget(self.details, 1)
        self._set_document_actions_enabled(False)

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

    def show_document_details(self, document: DocumentModel | None):
        self.details.set_document(document)

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

    def _on_selection_changed(self):
        document_id = self.selected_document_id()
        self._set_document_actions_enabled(document_id is not None)
        if document_id is not None:
            self.document_selected.emit(document_id)

    def _set_document_actions_enabled(self, enabled: bool):
        self.details.set_actions_enabled(enabled)

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
