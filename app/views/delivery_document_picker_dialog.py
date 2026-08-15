from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout


class DeliveryDocumentPickerDialog(QDialog):
    """Explorador lógico do GED; nunca revela o filesystem gerenciado."""
    def __init__(self, documents, folders, parent=None):
        super().__init__(parent); self.setWindowTitle("Selecionar documentos do SmartFile"); self.resize(620,480)
        layout=QVBoxLayout(self); layout.addWidget(QLabel("Selecione documentos da organização ativa:"))
        self.tree=QTreeWidget(); self.tree.setHeaderLabels(["Pasta / documento","Tipo","Tamanho"]); self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        roots={None:self.tree.invisibleRootItem()}; by_parent={}
        for folder in folders: by_parent.setdefault(folder.parent_id,[]).append(folder)
        def add(parent_id,parent_item):
            for folder in by_parent.get(parent_id,[]):
                item=QTreeWidgetItem(parent_item,[folder.name,"Pasta",""]); item.setData(0,Qt.ItemDataRole.UserRole,None); roots[folder.id]=item; add(folder.id,item)
        add(None,roots[None])
        for document in documents:
            parent=roots.get(document.folder_id,roots[None]); item=QTreeWidgetItem(parent,[document.name,document.file_type or document.extension,f"{document.size/1024:.1f} KB"]); item.setData(0,Qt.ItemDataRole.UserRole,document.id)
        self.tree.expandAll(); layout.addWidget(self.tree)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def selected_document_ids(self): return [int(item.data(0,Qt.ItemDataRole.UserRole)) for item in self.tree.selectedItems() if item.data(0,Qt.ItemDataRole.UserRole) is not None]
