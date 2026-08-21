from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider


class DeliveryDocumentPickerDialog(QDialog):
    """Explorador do catálogo lógico do GED, sem exposição do storage físico."""

    KIND_ROLE = Qt.ItemDataRole.UserRole
    ID_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(
        self, documents, folders, parent=None, *, organization_name="Minha Organização",
        already_selected=None,
    ):
        super().__init__(parent)
        self.setObjectName("deliveryDocumentPicker")
        self.setWindowTitle("Selecionar documentos do SmartFile")
        self.resize(1040, 680)
        self.setMinimumSize(760, 520)
        self._documents = list(documents)
        self._folders = list(folders)
        self._organization_name = organization_name
        self._folders_by_id = {folder.id: folder for folder in self._folders}
        self._selected_ids = {int(value) for value in (already_selected or [])}
        self._current_folder_id = None
        self._populating = False
        self._tree_items = {}
        self._setup_ui()
        self._populate_tree()
        self._show_folder(None)

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)
        title = QLabel("Selecionar documentos do SmartFile")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "Navegue pelas pastas lógicas e selecione os documentos que deseja adicionar à cesta."
        )
        subtitle.setWordWrap(True)
        root.addWidget(title); root.addWidget(subtitle)

        navigation = QHBoxLayout()
        self.back_button = QPushButton("Voltar")
        IconProvider.apply(self.back_button, "pdf_back")
        self.back_button.setAccessibleName("Voltar para a pasta anterior")
        self.back_button.clicked.connect(self.go_back)
        self.breadcrumb = QLabel(); self.breadcrumb.setObjectName("pickerBreadcrumb")
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar nesta pasta...")
        self.search.setClearButtonEnabled(True); self.search.textChanged.connect(self._filter_rows)
        navigation.addWidget(self.back_button); navigation.addWidget(self.breadcrumb, 1); navigation.addWidget(self.search)
        root.addLayout(navigation)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        folders_panel = QWidget(); folders_layout = QVBoxLayout(folders_panel)
        folders_layout.setContentsMargins(0, 0, 6, 0); folders_layout.addWidget(QLabel("Pastas"))
        self.folder_tree = QTreeWidget(); self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.folder_tree.currentItemChanged.connect(self._tree_folder_changed)
        folders_layout.addWidget(self.folder_tree); splitter.addWidget(folders_panel)

        content_panel = QWidget(); content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(6, 0, 0, 0)
        self.folder_title = QLabel(); self.folder_title.setObjectName("pickerFolderTitle")
        self.item_count = QLabel(); content_layout.addWidget(self.folder_title); content_layout.addWidget(self.item_count)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nome", "Tipo", "Tamanho", "Modificado em"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True); self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in (1, 2, 3):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.table.itemDoubleClicked.connect(self._open_item)
        content_layout.addWidget(self.table, 1)
        self.empty_state = QLabel("Esta pasta está vazia.")
        self.empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state.setObjectName("pickerEmptyState"); content_layout.addWidget(self.empty_state)
        splitter.addWidget(content_panel); splitter.setSizes([280, 740]); root.addWidget(splitter, 1)

        footer = QHBoxLayout(); self.selection_status = QLabel()
        clear_button = QPushButton("Limpar seleção"); clear_button.clicked.connect(self.clear_selection)
        cancel_button = QPushButton("Cancelar"); cancel_button.clicked.connect(self.reject)
        self.add_button = QPushButton("Adicionar à cesta"); self.add_button.setObjectName("deliveryPrimary")
        IconProvider.apply(self.add_button, "import"); self.add_button.clicked.connect(self.accept)
        footer.addWidget(self.selection_status); footer.addWidget(clear_button); footer.addStretch()
        footer.addWidget(cancel_button); footer.addWidget(self.add_button); root.addLayout(footer)
        self._update_selection_status()

    def _populate_tree(self) -> None:
        self.folder_tree.clear()
        root_item = QTreeWidgetItem([self._organization_name])
        root_item.setData(0, self.ID_ROLE, None); root_item.setIcon(0, IconProvider.icon("organization"))
        self.folder_tree.addTopLevelItem(root_item); self._tree_items = {None: root_item}
        children = {}
        for folder in self._folders:
            children.setdefault(folder.parent_id, []).append(folder)

        def append(parent_id, parent_item) -> None:
            for folder in sorted(children.get(parent_id, []), key=lambda item: item.name.casefold()):
                item = QTreeWidgetItem([folder.name]); item.setData(0, self.ID_ROLE, folder.id)
                item.setIcon(0, IconProvider.icon("folder")); parent_item.addChild(item)
                self._tree_items[folder.id] = item; append(folder.id, item)

        append(None, root_item); root_item.setExpanded(True); self.folder_tree.setCurrentItem(root_item)

    def _show_folder(self, folder_id) -> None:
        self._capture_current_selection(); self._current_folder_id = folder_id; self._populating = True
        self.table.setRowCount(0)
        child_folders = sorted(
            (item for item in self._folders if item.parent_id == folder_id),
            key=lambda item: item.name.casefold(),
        )
        documents = sorted(
            (item for item in self._documents if item.folder_id == folder_id),
            key=lambda item: item.name.casefold(),
        )
        for folder in child_folders:
            self._append_row(folder.name, "Pasta", "—", folder.updated_at or "", "folder", folder.id)
        for document in documents:
            self._append_row(
                document.name, document.file_type or document.extension.lstrip(".").upper(),
                self._format_size(document.size),
                (document.updated_at or document.created_at or "").replace("T", " ")[:16],
                "document", document.id,
            )
        self._populating = False
        self.folder_title.setText(self._organization_name if folder_id is None else self._folders_by_id[folder_id].name)
        self.item_count.setText(f"{len(child_folders) + len(documents)} item(ns)")
        self.breadcrumb.setText("  ›  ".join(self._breadcrumb_names(folder_id)))
        self.back_button.setEnabled(folder_id is not None)
        self.empty_state.setVisible(self.table.rowCount() == 0); self.table.setVisible(self.table.rowCount() > 0)
        self.search.clear()
        tree_item = self._tree_items.get(folder_id)
        if tree_item is not None and self.folder_tree.currentItem() is not tree_item:
            self.folder_tree.blockSignals(True); self.folder_tree.setCurrentItem(tree_item)
            self.folder_tree.scrollToItem(tree_item); self.folder_tree.blockSignals(False)
        self._restore_current_selection(); self._update_selection_status()

    def _append_row(self, name, kind_label, size, updated, kind, item_id) -> None:
        row = self.table.rowCount(); self.table.insertRow(row)
        name_item = QTableWidgetItem(name); name_item.setData(self.KIND_ROLE, kind); name_item.setData(self.ID_ROLE, item_id)
        icon = "folder" if kind == "folder" else "pdf" if kind_label == "PDF" else "documents"
        name_item.setIcon(IconProvider.icon(icon)); self.table.setItem(row, 0, name_item)
        for column, value in enumerate((kind_label, size, updated), start=1):
            item = QTableWidgetItem(value); item.setData(self.KIND_ROLE, kind); item.setData(self.ID_ROLE, item_id)
            self.table.setItem(row, column, item)

    def _tree_folder_changed(self, current, _previous) -> None:
        if current is not None:
            self._show_folder(current.data(0, self.ID_ROLE))

    def _open_item(self, item) -> None:
        if item.data(self.KIND_ROLE) == "folder":
            self._show_folder(item.data(self.ID_ROLE))

    def go_back(self) -> None:
        if self._current_folder_id is None: return
        current = self._folders_by_id.get(self._current_folder_id)
        self._show_folder(current.parent_id if current else None)

    def clear_selection(self) -> None:
        self._selected_ids.clear(); self.table.clearSelection(); self._update_selection_status()

    def _selection_changed(self) -> None:
        if not self._populating:
            self._capture_current_selection(); self._update_selection_status()

    def _capture_current_selection(self) -> None:
        visible_ids = {
            int(self.table.item(row, 0).data(self.ID_ROLE)) for row in range(self.table.rowCount())
            if self.table.item(row, 0).data(self.KIND_ROLE) == "document"
        }
        selected = {
            int(item.data(self.ID_ROLE)) for item in self.table.selectedItems()
            if item.column() == 0 and item.data(self.KIND_ROLE) == "document"
        }
        self._selected_ids.difference_update(visible_ids); self._selected_ids.update(selected)

    def _restore_current_selection(self) -> None:
        self._populating = True
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item.data(self.KIND_ROLE) == "document" and int(item.data(self.ID_ROLE)) in self._selected_ids:
                for column in range(self.table.columnCount()):
                    self.table.item(row, column).setSelected(True)
        self._populating = False

    def _filter_rows(self, text: str) -> None:
        term = text.strip().casefold(); visible = 0
        for row in range(self.table.rowCount()):
            matched = not term or term in self.table.item(row, 0).text().casefold()
            self.table.setRowHidden(row, not matched); visible += int(matched)
        self.empty_state.setText("Nenhum item corresponde à busca." if term else "Esta pasta está vazia.")
        self.empty_state.setVisible(visible == 0); self.table.setVisible(visible > 0)

    def _breadcrumb_names(self, folder_id) -> list[str]:
        names = []; current = self._folders_by_id.get(folder_id)
        while current is not None:
            names.append(current.name); current = self._folders_by_id.get(current.parent_id)
        return [self._organization_name, *reversed(names)]

    def selected_document_ids(self) -> list[int]:
        self._capture_current_selection(); return sorted(self._selected_ids)

    def _update_selection_status(self) -> None:
        count = len(self._selected_ids); self.selection_status.setText(f"{count} documento(s) selecionado(s)")
        self.add_button.setEnabled(count > 0)

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                text = f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"
                return text.replace(".", ",")
            value /= 1024
        return f"{size} B"
