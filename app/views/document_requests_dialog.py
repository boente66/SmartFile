from __future__ import annotations

from PyQt6.QtCore import QDateTime, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QTextEdit, QVBoxLayout,
)


class DocumentRequestsDialog(QDialog):
    """View passiva para solicitações documentais.

    A view coleta dados e emite intenções. Carregamento, permissões e regras de
    negócio pertencem ao ``DocumentRequestController`` e ao service.
    """

    create_requested = pyqtSignal(dict)
    status_update_requested = pyqtSignal(int, str)
    STATUS_LABELS = {
        "OPEN": "Aberta", "IN_PROGRESS": "Em atendimento", "ATTENDED": "Atendida",
        "DELIVERING": "Em entrega", "DELIVERED": "Entregue", "COMPLETED": "Concluída",
        "CANCELLED": "Cancelada", "OVERDUE": "Atrasada",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
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
        self.use_due = QCheckBox("Definir prazo")
        self.due = QDateTimeEdit(QDateTime.currentDateTime().addDays(7))
        self.due.setCalendarPopup(True); self.due.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.set_deadline_enabled(False)
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
        self.set_permissions(can_create=False, can_update=False)
        actions.addWidget(self.create_button); actions.addStretch(); actions.addWidget(self.status); actions.addWidget(self.update_button)
        root.addLayout(actions)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject); root.addWidget(buttons)
    def set_requests(self, requests) -> None:
        self.list.clear()
        for request in requests:
            due = request.due_at[:16].replace("T", " ") if request.due_at else "sem prazo"
            assignee = self._assignee_names.get(request.assigned_to_user_id, "sem responsável")
            item = QListWidgetItem(
                f"{self.STATUS_LABELS.get(request.status, request.status)} · "
                f"{request.title} · {assignee} · {due}"
            )
            item.setData(256, request.id); item.setData(257, request.status); self.list.addItem(item)

    def set_assignable_members(self, users) -> None:
        selected = self.assignee.currentData()
        self.assignee.clear()
        self.assignee.addItem("Sem responsável", None)
        self._assignee_names = {}
        for user in users:
            self.assignee.addItem(user.display_name, user.id)
            self._assignee_names[user.id] = user.display_name
        index = self.assignee.findData(selected)
        if index >= 0:
            self.assignee.setCurrentIndex(index)

    def set_permissions(self, *, can_create: bool, can_update: bool) -> None:
        self.create_button.setEnabled(can_create)
        self.update_button.setEnabled(can_update)
        self.status.setEnabled(can_update)

    def set_deadline_enabled(self, enabled: bool) -> None:
        self.use_due.setEnabled(enabled)
        self.use_due.setChecked(enabled)
        self.due.setEnabled(enabled)

    def clear_create_form(self) -> None:
        self.title.clear()
        self.description.clear()

    def show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Solicitações", message)

    def _create(self) -> None:
        self.create_requested.emit({
            "title": self.title.text(),
            "description": self.description.toPlainText(),
            "assigned_to_user_id": self.assignee.currentData(),
            "due_at": (
                    self.due.dateTime().toPyDateTime().astimezone().isoformat()
                    if self.use_due.isChecked() else None
            ),
        })

    def _update_status(self) -> None:
        item = self.list.currentItem()
        if item is None: return
        self.status_update_requested.emit(
            int(item.data(256)), str(self.status.currentData())
        )

    def _selection_changed(self, current, _previous) -> None:
        if current is None: return
        index = self.status.findData(current.data(257))
        if index >= 0: self.status.setCurrentIndex(index)
