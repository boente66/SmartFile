from __future__ import annotations

from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout,
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
        note = QLabel(
            "Solicitações documentais opcionais. Este recurso não representa chamados de TI."
        )
        note.setWordWrap(True); root.addWidget(note)
        self.list = QListWidget(); self.list.currentItemChanged.connect(self._selection_changed)
        root.addWidget(self.list, 1)
        form = QFormLayout()
        self.title = QLineEdit(); self.description = QTextEdit(); self.description.setMaximumHeight(70)
        self.assignee = QComboBox(); self.assignee.addItem("Sem responsável", None)
        self._assignee_names = {}
        for user in self.service.list_assignable_members(organization_id):
            self.assignee.addItem(user.display_name, user.id)
            self._assignee_names[user.id] = user.display_name
        self.use_due = QCheckBox("Definir prazo")
        self.due = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy HH:mm")
        deadline_enabled = self.service.deadline_enabled(organization_id)
        self.use_due.setEnabled(deadline_enabled)
        self.use_due.setChecked(deadline_enabled)
        self.due.setEnabled(deadline_enabled)
        self.use_due.toggled.connect(self.due.setEnabled)
        form.addRow("Documento solicitado:", self.title)
        form.addRow("Descrição:", self.description)
        form.addRow("Responsável:", self.assignee)
        form.addRow("", self.use_due); form.addRow("Prazo:", self.due)
        root.addLayout(form)
        actions = QHBoxLayout()
        self.create_button = QPushButton("Criar solicitação"); self.create_button.clicked.connect(self._create)
        self.status = QComboBox()
        for code, label in self.STATUS_LABELS.items(): self.status.addItem(label, code)
        self.update_button = QPushButton("Atualizar estado"); self.update_button.clicked.connect(self._update_status)
        self.create_button.setEnabled(self.service.can_create())
        self.update_button.setEnabled(self.service.can_update())
        self.status.setEnabled(self.service.can_update())
        actions.addWidget(self.create_button); actions.addStretch(); actions.addWidget(self.status); actions.addWidget(self.update_button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._refresh()

    def _refresh(self) -> None:
        self.list.clear()
        for request in self.service.list_requests(self.organization_id):
            due = request.due_at[:16].replace("T", " ") if request.due_at else "sem prazo"
            assignee = self._assignee_names.get(request.assigned_to_user_id, "sem responsável")
            item = QListWidgetItem(
                f"{self.STATUS_LABELS.get(request.status, request.status)} · "
                f"{request.title} · {assignee} · {due}"
            )
            item.setData(256, request.id); item.setData(257, request.status); self.list.addItem(item)

    def _create(self) -> None:
        try:
            self.service.create(
                self.organization_id, self.title.text(), self.description.toPlainText(),
                assigned_to_user_id=self.assignee.currentData(),
                due_at=(
                    self.due.dateTime().toPyDateTime().astimezone().isoformat()
                    if self.use_due.isChecked() else None
                ),
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
