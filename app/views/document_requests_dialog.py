from __future__ import annotations

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)


class DocumentRequestsDialog(QDialog):
    STATUS_LABELS = {
        "OPEN": "Aberta", "IN_PROGRESS": "Em andamento", "COMPLETED": "Concluída",
        "CANCELLED": "Cancelada", "OVERDUE": "Atrasada",
    }

    def __init__(self, service, organization_id: int, parent=None):
        super().__init__(parent)
        self.service = service; self.organization_id = organization_id
        self.setWindowTitle("Solicitações de documentos")
        self.resize(760, 560)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Solicitações, responsáveis e temporizadores da organização"))
        self.list = QListWidget(); self.list.currentItemChanged.connect(self._selection_changed)
        root.addWidget(self.list, 1)
        form = QFormLayout()
        self.title = QLineEdit(); self.description = QTextEdit(); self.description.setMaximumHeight(70)
        self.due = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy HH:mm")
        form.addRow("Documento solicitado:", self.title)
        form.addRow("Descrição:", self.description); form.addRow("Prazo:", self.due)
        root.addLayout(form)
        actions = QHBoxLayout()
        create = QPushButton("Criar solicitação"); create.clicked.connect(self._create)
        self.status = QComboBox()
        for code, label in self.STATUS_LABELS.items(): self.status.addItem(label, code)
        update = QPushButton("Atualizar estado"); update.clicked.connect(self._update_status)
        actions.addWidget(create); actions.addStretch(); actions.addWidget(self.status); actions.addWidget(update)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.list.clear()
        for request in self.service.list_requests(self.organization_id):
            due = request.due_at[:16].replace("T", " ") if request.due_at else "sem prazo"
            item = QListWidgetItem(
                f"{self.STATUS_LABELS.get(request.status, request.status)} · {request.title} · {due}"
            )
            item.setData(256, request.id); item.setData(257, request.status); self.list.addItem(item)

    def _create(self) -> None:
        try:
            self.service.create(
                self.organization_id, self.title.text(), self.description.toPlainText(),
                due_at=self.due.dateTime().toPyDateTime().astimezone().isoformat(),
            )
            self.title.clear(); self.description.clear(); self._refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Solicitações", str(exc))

    def _update_status(self) -> None:
        item = self.list.currentItem()
        if item is None: return
        try:
            self.service.set_status(self.organization_id, int(item.data(256)), str(self.status.currentData()))
            self._refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Solicitações", str(exc))

    def _selection_changed(self, current, _previous) -> None:
        if current is None: return
        index = self.status.findData(current.data(257))
        if index >= 0: self.status.setCurrentIndex(index)
