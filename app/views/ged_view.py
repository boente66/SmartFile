from PyQt6.QtCore import Qt, pyqtSignal as Signal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QInputDialog,
)


class GEDView(QWidget):
    """Vista de Mini GED para organização visual de documentos."""

    folder_requested = Signal()
    refresh_requested = Signal()
    open_requested = Signal(str)
    rename_requested = Signal(str, str)
    delete_requested = Signal(str)

    def __init__(self):
        super().__init__()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("Mini GED")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)

        intro = QLabel(
            "Organize, encontre e renomeie os documentos gerados pelo conversor, scanner e PDF Tools em um só lugar."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("Selecione uma pasta")

        btn_folder = QPushButton("Escolher pasta")
        btn_folder.clicked.connect(self.folder_requested.emit)

        controls.addWidget(QLabel("Pasta"))
        controls.addWidget(self.folder_edit, 1)
        controls.addWidget(btn_folder)
        layout.addLayout(controls)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por nome")
        self.search_edit.textChanged.connect(lambda _: self.refresh_requested.emit())

        btn_refresh = QPushButton("Atualizar")
        btn_refresh.clicked.connect(self.refresh_requested.emit)

        search_layout.addWidget(QLabel("Buscar"))
        search_layout.addWidget(self.search_edit, 1)
        search_layout.addWidget(btn_refresh)
        layout.addLayout(search_layout)

        actions = QHBoxLayout()
        self.btn_open = QPushButton("Abrir")
        self.btn_open.clicked.connect(self._request_open)

        self.btn_rename = QPushButton("Renomear")
        self.btn_rename.clicked.connect(self._request_rename)

        self.btn_delete = QPushButton("Excluir")
        self.btn_delete.clicked.connect(self._request_delete)

        actions.addWidget(self.btn_open)
        actions.addWidget(self.btn_rename)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)

        self.summary_label = QLabel("Nenhuma pasta selecionada")
        layout.addWidget(self.summary_label)

        self.doc_tree = QTreeWidget()
        self.doc_tree.setHeaderLabels(["Nome", "Tipo", "Tamanho", "Alterado"])
        self.doc_tree.setAlternatingRowColors(True)
        self.doc_tree.setColumnWidth(0, 240)
        self.doc_tree.setColumnWidth(1, 110)
        self.doc_tree.setColumnWidth(2, 90)
        self.doc_tree.setColumnWidth(3, 160)
        layout.addWidget(self.doc_tree, 1)

    def set_folder(self, path: str):
        self.folder_edit.setText(path)

    def set_documents(self, documents: list[dict]):
        self.doc_tree.clear()
        for item_data in documents:
            row = QTreeWidgetItem(
                [
                    item_data["name"],
                    item_data["kind"],
                    item_data["size"],
                    item_data["modified"],
                ]
            )
            row.setData(0, Qt.ItemDataRole.UserRole, item_data["path"])
            self.doc_tree.addTopLevelItem(row)

    def set_summary(self, text: str):
        self.summary_label.setText(text)

    def search_text(self) -> str:
        return self.search_edit.text().strip()

    def selected_path(self) -> str | None:
        selected = self.doc_tree.selectedItems()
        if not selected:
            return None
        return selected[0].data(0, Qt.ItemDataRole.UserRole)

    def _request_open(self):
        path = self.selected_path()
        if path:
            self.open_requested.emit(path)

    def _request_rename(self):
        path = self.selected_path()
        if not path:
            return

        current_name = path.split("/")[-1]

        new_name, ok = QInputDialog.getText(
            self,
            "Renomear documento",
            "Novo nome:",
            text=current_name,
        )

        if ok and new_name.strip():
            self.rename_requested.emit(path, new_name.strip())

    def _request_delete(self):
        path = self.selected_path()
        if path:
            self.delete_requested.emit(path)
