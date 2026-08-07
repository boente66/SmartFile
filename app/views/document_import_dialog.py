from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QPushButton, QSplitter, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.ui.icon_provider import IconProvider


class DocumentImportDialog(QDialog):
    """Explorador simplificado: arquivos locais à direita e pastas lógicas à esquerda."""

    def __init__(self, organization_name: str, folders, current_folder_id=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adicionar documentos ao SmartFile")
        self.resize(860, 560)
        self._paths: list[Path] = []
        root = QVBoxLayout(self)
        heading = QLabel("Escolha os arquivos e a pasta lógica de destino")
        heading.setObjectName("dialogTitle")
        root.addWidget(heading)
        hint = QLabel(
            "Os arquivos serão copiados para o armazenamento interno; a estrutura abaixo é lógica."
        )
        hint.setWordWrap(True)
        root.addWidget(hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        folder_panel = QWidget(); folder_layout = QVBoxLayout(folder_panel)
        folder_layout.addWidget(QLabel("Pastas da organização"))
        self.folder_tree = QTreeWidget(); self.folder_tree.setHeaderHidden(True)
        root_item = QTreeWidgetItem([organization_name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, None)
        root_item.setIcon(0, IconProvider.icon("organization"))
        self.folder_tree.addTopLevelItem(root_item)
        items = {}
        for folder in folders:
            item = QTreeWidgetItem([folder.name]); item.setIcon(0, IconProvider.icon("folder"))
            item.setData(0, Qt.ItemDataRole.UserRole, folder.id); items[folder.id] = item
        for folder in folders:
            items.get(folder.parent_id, root_item).addChild(items[folder.id])
        root_item.setExpanded(True); self.folder_tree.expandAll()
        self.folder_tree.setCurrentItem(items.get(current_folder_id, root_item))
        folder_layout.addWidget(self.folder_tree)
        splitter.addWidget(folder_panel)

        file_panel = QWidget(); file_layout = QVBoxLayout(file_panel)
        file_layout.addWidget(QLabel("Arquivos selecionados"))
        self.file_list = QListWidget(); file_layout.addWidget(self.file_list, 1)
        choose = QPushButton("Selecionar arquivos")
        IconProvider.apply(choose, "import")
        choose.clicked.connect(self._choose_files)
        remove = QPushButton("Remover selecionado")
        IconProvider.apply(remove, "action_trash")
        remove.clicked.connect(self._remove_selected)
        actions = QHBoxLayout(); actions.addWidget(choose); actions.addWidget(remove); actions.addStretch()
        file_layout.addLayout(actions)
        metadata = QFormLayout()
        self.category = QLineEdit(); self.category.setPlaceholderText("Ex.: Contratos")
        self.tags = QLineEdit(); self.tags.setPlaceholderText("Ex.: cliente, 2026, urgente")
        metadata.addRow("Categoria (opcional):", self.category)
        metadata.addRow("Etiquetas (opcional):", self.tags)
        file_layout.addLayout(metadata)
        splitter.addWidget(file_panel); splitter.setSizes([300, 540])
        root.addWidget(splitter, 1)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Adicionar ao GED")
        self.buttons.accepted.connect(self._accept_if_valid); self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def values(self) -> dict:
        item = self.folder_tree.currentItem()
        return {
            "paths": tuple(self._paths),
            "folder_id": item.data(0, Qt.ItemDataRole.UserRole) if item else None,
            "category": self.category.text().strip() or None,
            "tags": self.tags.text().strip() or None,
        }

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Selecionar documentos", "", "Todos os arquivos (*)")
        known = {str(path) for path in self._paths}
        for value in paths:
            path = Path(value).expanduser().resolve()
            if str(path) not in known:
                self._paths.append(path); self.file_list.addItem(path.name); known.add(str(path))

    def _remove_selected(self) -> None:
        for row in sorted({item.row() for item in self.file_list.selectedIndexes()}, reverse=True):
            self.file_list.takeItem(row); self._paths.pop(row)

    def _accept_if_valid(self) -> None:
        if not self._paths:
            self.file_list.setToolTip("Selecione pelo menos um arquivo.")
            self.file_list.setFocus(); return
        self.accept()
