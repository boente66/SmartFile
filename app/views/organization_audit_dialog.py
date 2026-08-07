from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHeaderView, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


class OrganizationAuditDialog(QDialog):
    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histórico auditável da organização")
        self.resize(900, 520)
        root = QVBoxLayout(self)
        table = QTableWidget(len(rows), 3)
        table.setHorizontalHeaderLabels(["Data e hora", "Ação", "Descrição"])
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for index, row in enumerate(rows):
            values = (
                row.created_at[:19].replace("T", " "),
                row.action,
                row.description or "",
            )
            for column, value in enumerate(values):
                table.setItem(index, column, QTableWidgetItem(value))
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        root.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
