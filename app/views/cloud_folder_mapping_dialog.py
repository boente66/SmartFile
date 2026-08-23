from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout,
)

from app.cloud.cloud_models import RemoteMetadata
from app.ui.icon_provider import IconProvider
from app.workers.cloud_folder_worker import CloudFolderBrowseWorker


class CloudFolderMappingDialog(QDialog):
    """Navegador assíncrono de pastas; remote_id permanece a identidade real."""

    _live_workers: set[CloudFolderBrowseWorker] = set()

    def __init__(
        self, provider, logical_path: str, account_label: str, parent=None,
    ):
        super().__init__(parent)
        self.provider = provider
        self._worker: CloudFolderBrowseWorker | None = None
        self._selected: RemoteMetadata | None = None
        self.setWindowTitle("Mapear pasta do OneDrive")
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        title = QLabel("Mapear pasta do OneDrive")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        form = QFormLayout()
        form.addRow("Pasta SmartFile:", QLabel(logical_path))
        form.addRow("Conta:", QLabel(account_label))
        layout.addLayout(form)
        layout.addWidget(QLabel("Escolha uma pasta existente no OneDrive:"))

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemExpanded.connect(self._on_expanded)
        self.tree.currentItemChanged.connect(self._on_selected)
        layout.addWidget(self.tree, 1)
        self.root_item = QTreeWidgetItem(["OneDrive"])
        self.root_item.setIcon(0, IconProvider.icon("cloud_add"))
        self.root_item.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        self.root_item.addChild(QTreeWidgetItem(["Carregando…"]))
        self.tree.addTopLevelItem(self.root_item)

        self.selection_label = QLabel("Pasta selecionada: —")
        self.selection_label.setWordWrap(True)
        layout.addWidget(self.selection_label)
        self.state_label = QLabel("Carregando…")
        self.state_label.setObjectName("cloudFolderMappingState")
        layout.addWidget(self.state_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        self.map_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.map_button.setText("Mapear pasta")
        self.map_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.root_item.setExpanded(True)
        self._load(self.root_item, None)

    def selected_folder(self) -> RemoteMetadata | None:
        return self._selected

    def _on_expanded(self, item: QTreeWidgetItem) -> None:
        if not bool(item.data(0, Qt.ItemDataRole.UserRole + 1)):
            metadata = item.data(0, Qt.ItemDataRole.UserRole)
            self._load(item, metadata.remote_id if metadata else None)

    def _load(self, target: QTreeWidgetItem, parent_id: str | None) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        target.setData(0, Qt.ItemDataRole.UserRole + 1, True)
        target.takeChildren()
        self.state_label.setText("Carregando…")
        self.tree.setEnabled(False)
        worker = CloudFolderBrowseWorker(self.provider, parent_id)
        self._worker = worker
        self._live_workers.add(worker)
        worker.succeeded.connect(
            lambda _parent, folders, t=target, w=worker: self._loaded(t, folders, w)
        )
        worker.failed.connect(
            lambda _parent, message, t=target, w=worker: self._failed(t, message, w)
        )
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _loaded(
        self, target: QTreeWidgetItem, folders: list[RemoteMetadata], worker,
    ) -> None:
        if worker is not self._worker:
            return
        for folder in sorted(folders, key=lambda item: item.name.casefold()):
            child = QTreeWidgetItem([folder.name])
            child.setIcon(0, IconProvider.icon("folder"))
            child.setData(0, Qt.ItemDataRole.UserRole, folder)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, False)
            child.addChild(QTreeWidgetItem(["Carregando…"]))
            target.addChild(child)
        self.tree.setEnabled(True)
        self.state_label.setText(
            "Pasta vazia" if not folders else f"{len(folders)} pasta(s) encontrada(s)"
        )

    def _failed(self, target: QTreeWidgetItem, message: str, worker) -> None:
        if worker is not self._worker:
            return
        target.setData(0, Qt.ItemDataRole.UserRole + 1, False)
        target.addChild(QTreeWidgetItem(["Tentar novamente…"]))
        self.tree.setEnabled(True)
        self.state_label.setText(message)

    def _on_selected(self, item: QTreeWidgetItem | None, _previous) -> None:
        metadata = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self._selected = metadata if isinstance(metadata, RemoteMetadata) else None
        self.map_button.setEnabled(self._selected is not None)
        self.selection_label.setText(
            f"Pasta selecionada: {self._item_path(item)}"
            if self._selected else "Pasta selecionada: —"
        )

    @staticmethod
    def _item_path(item: QTreeWidgetItem | None) -> str:
        parts: list[str] = []
        while item is not None:
            parts.append(item.text(0))
            item = item.parent()
        return " / ".join(reversed(parts))

    def _cleanup_worker(self, worker) -> None:
        self._live_workers.discard(worker)
        if self._worker is worker:
            self._worker = None

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
        super().reject()
