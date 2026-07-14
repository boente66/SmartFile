from __future__ import annotations

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QLineEdit, QTextEdit, QVBoxLayout,
)


class ScannerImportDialog(QDialog):
    """Coleta metadados; não persiste nem manipula arquivos."""

    def __init__(self, document_service, parent=None, allowed_organization_ids=None):
        super().__init__(parent)
        self.service = document_service
        self.setWindowTitle("Adicionar digitalização ao GED")
        self.resize(520, 540)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.organization = QComboBox()
        allowed = set(allowed_organization_ids or [])
        for item in self.service.organization_service.list_organizations():
            if allowed and item.id not in allowed:
                continue
            self.organization.addItem(item.name, item.id)
        active_index = self.organization.findData(self.service.active_organization_id)
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
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Save
        )
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
        folders = self.service.folder_service.list_folders(int(organization_id))
        by_id = {folder.id: folder for folder in folders}
        for folder in folders:
            parts = [folder.name]
            parent = by_id.get(folder.parent_id)
            while parent:
                parts.insert(0, parent.name)
                parent = by_id.get(parent.parent_id)
            self.folder.addItem(" / ".join(parts), folder.id)

    def _accept_valid(self) -> None:
        if self.title.text().strip():
            self.accept()
        else:
            self.title.setFocus()
