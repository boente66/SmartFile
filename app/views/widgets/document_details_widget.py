from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models.document_model import DocumentModel
from app.ui.icon_provider import IconProvider


class DocumentDetailsWidget(QFrame):
    """Painel de apresentação e ações de um documento já carregado."""

    open_requested = pyqtSignal(int)
    convert_requested = pyqtSignal(int)
    pdf_tools_requested = pyqtSignal(int)
    trash_requested = pyqtSignal(int)
    favorite_requested = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._document_id: int | None = None
        self.setObjectName("documentDetailsPanel")
        self._value_labels: dict[str, QLabel] = {}
        self._setup_ui()
        self.set_document(None)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.title_label = QLabel("Detalhes do documento")
        self.title_label.setObjectName("documentDetailsTitle")
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.original_name_label = QLabel("Selecione um documento na tabela")
        self.original_name_label.setObjectName("documentDetailsSubtitle")
        self.original_name_label.setWordWrap(True)
        layout.addWidget(self.original_name_label)

        scroll = QScrollArea()
        scroll.setObjectName("documentDetailsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("documentDetailsContent")
        form = QFormLayout(content)
        form.setContentsMargins(0, 8, 0, 8)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        fields = (
            ("category", "Categoria"),
            ("file_type", "Tipo"),
            ("extension", "Extensão"),
            ("size", "Tamanho"),
            ("created_at", "Data de inclusão"),
            ("updated_at", "Última alteração"),
            ("last_accessed_at", "Último acesso"),
            ("tags", "Etiquetas"),
            ("checksum", "Checksum (SHA-256)"),
            ("path", "Localização"),
            ("favorite", "Favorito"),
        )
        for key, caption in fields:
            value = QLabel("—")
            value.setWordWrap(True)
            value.setTextInteractionFlags(value.textInteractionFlags())
            value.setObjectName("documentDetailValue")
            self._value_labels[key] = value
            form.addRow(f"{caption}:", value)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        primary_actions = QHBoxLayout()
        self.btn_open = QPushButton("Abrir")
        self.btn_open.setObjectName("primary")
        IconProvider.apply(self.btn_open, "open")
        self.btn_open.clicked.connect(lambda: self._emit(self.open_requested))
        self.btn_favorite = QPushButton("Favorito")
        IconProvider.apply(self.btn_favorite, "star")
        self.btn_favorite.clicked.connect(lambda: self._emit(self.favorite_requested))
        primary_actions.addWidget(self.btn_open, 1)
        primary_actions.addWidget(self.btn_favorite, 1)
        layout.addLayout(primary_actions)

        secondary_actions = QHBoxLayout()
        self.btn_convert = QPushButton("Converter")
        IconProvider.apply(self.btn_convert, "converter")
        self.btn_convert.clicked.connect(lambda: self._emit(self.convert_requested))
        self.btn_pdf = QPushButton("PDF Tools")
        IconProvider.apply(self.btn_pdf, "pdf")
        self.btn_pdf.clicked.connect(lambda: self._emit(self.pdf_tools_requested))
        secondary_actions.addWidget(self.btn_convert, 1)
        secondary_actions.addWidget(self.btn_pdf, 1)
        layout.addLayout(secondary_actions)

        self.btn_trash = QPushButton("Remover do catálogo")
        self.btn_trash.setObjectName("dangerAction")
        IconProvider.apply(self.btn_trash, "trash")
        self.btn_trash.clicked.connect(lambda: self._emit(self.trash_requested))
        layout.addWidget(self.btn_trash)

        self._action_buttons = (
            self.btn_open,
            self.btn_favorite,
            self.btn_convert,
            self.btn_pdf,
            self.btn_trash,
        )

    def set_document(self, document: DocumentModel | None) -> None:
        self._document_id = document.id if document and document.id else None
        enabled = self._document_id is not None
        for button in self._action_buttons:
            button.setEnabled(enabled)

        if document is None:
            self.title_label.setText("Detalhes do documento")
            self.original_name_label.setText("Selecione um documento na tabela")
            for label in self._value_labels.values():
                label.setText("—")
            return

        self.title_label.setText(document.name)
        self.original_name_label.setText(document.original_name or document.name)
        values = {
            "category": document.category,
            "file_type": document.file_type,
            "extension": document.extension,
            "size": self._format_size(document.size),
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "last_accessed_at": document.last_accessed_at,
            "tags": document.tags,
            "checksum": document.checksum,
            "path": document.path,
            "favorite": "Sim" if document.favorite else "Não",
        }
        for key, value in values.items():
            self._value_labels[key].setText(str(value) if value else "—")

    def set_actions_enabled(self, enabled: bool) -> None:
        for button in self._action_buttons:
            button.setEnabled(enabled and self._document_id is not None)

    def _emit(self, signal) -> None:
        if self._document_id is not None:
            signal.emit(self._document_id)

    @staticmethod
    def _format_size(size: int | None) -> str:
        if size is None:
            return "—"
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.0f} {unit}"
            value /= 1024
        return "—"
