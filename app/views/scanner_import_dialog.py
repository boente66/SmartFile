from __future__ import annotations

from app.views.widgets.dialog_theme import apply_import_theme

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QTextEdit, QVBoxLayout, QLabel,
)


class ScannerImportDialog(QDialog):
    """Coleta metadados; não persiste nem manipula arquivos."""

    def __init__(self, organizations, folders_by_organization, active_organization_id=None, parent=None):
        super().__init__(parent)
        apply_import_theme(self)
        self._folders = folders_by_organization
        self.setWindowTitle("Adicionar digitalização ao GED")
        self.resize(520, 540)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.organization = QComboBox()
        for item in organizations:
            self.organization.addItem(item.name, item.id)
        active_index = self.organization.findData(active_organization_id)
        self.organization.setCurrentIndex(max(0, active_index))
        self.organization.currentIndexChanged.connect(self._load_folders)
        self.folder = QComboBox()
        self.title = QLineEdit("Documento digitalizado")
        self.category = QLineEdit("Documento")
        self.description = QTextEdit()
        self.description.setMaximumHeight(70)
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("Separe as etiquetas por vírgula")
        self.document_date = QDateEdit(QDate.currentDate())
        self.document_date.setCalendarPopup(True)
        self.notes = QTextEdit()
        self.notes.setMaximumHeight(60)
        self.sync_cloud = QCheckBox("Sincronizar com a nuvem vinculada")
        self.sync_cloud.setChecked(True)
        form.addRow("Organização:", self.organization)
        form.addRow("Pasta lógica:", self.folder)
        form.addRow("Título:", self.title)
        form.addRow("Categoria:", self.category)
        form.addRow("Descrição:", self.description)
        form.addRow("Etiquetas:", self.tags)
        form.addRow("Data do documento:", self.document_date)
        form.addRow("Observações:", self.notes)
        form.addRow("", self.sync_cloud)
        root.addLayout(form)
        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Adicionar ao GED")
        buttons.accepted.connect(self._accept_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._load_folders()

    def values(self) -> dict:
        return {
            "organization_id": int(self.organization.currentData()),
            "folder_id": self.folder.currentData(),
            "title": self.title.text().strip(),
            "category": self.category.text().strip() or None,
            "description": self.description.toPlainText().strip() or None,
            "tags": self.tags.text().strip() or None,
            "document_date": self.document_date.date().toString("yyyy-MM-dd"),
            "notes": self.notes.toPlainText().strip() or None,
            "source_type": "SCANNER",
            "sync_cloud": self.sync_cloud.isChecked(),
        }

    def _load_folders(self) -> None:
        organization_id = self.organization.currentData()
        self.folder.clear()
        self.folder.addItem("Sem pasta", None)
        if organization_id is None:
            return
        folders = self._folders.get(int(organization_id), [])
        by_id = {folder.id: folder for folder in folders}
        for folder in folders:
            parts = [folder.name]
            parent = by_id.get(folder.parent_id)
            visited = {folder.id}
            while parent and parent.id not in visited:
                visited.add(parent.id)
                parts.insert(0, parent.name)
                parent = by_id.get(parent.parent_id)
            self.folder.addItem(" / ".join(parts), folder.id)

    def _accept_valid(self) -> None:
        if self.organization.currentData() is None:
            self.error_label.setText("Selecione uma organização disponível.")
        elif self.title.text().strip():
            self.accept()
        else:
            self.error_label.setText("Informe o título do documento.")
            self.title.setFocus()
