from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFormLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.models.pdf_document_info import PDFDocumentInfo


class PDFInfoPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._labels = {}
        root = QVBoxLayout(self)
        heading = QLabel("Informações do documento")
        heading.setObjectName("pdfViewerPanelTitle")
        root.addWidget(heading)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        fields = (
            ("name", "Nome"), ("path", "Caminho"), ("size", "Tamanho"),
            ("page_count", "Páginas"), ("title", "Título"), ("author", "Autor"),
            ("subject", "Assunto"), ("keywords", "Palavras-chave"),
            ("creator", "Criador"), ("producer", "Produtor"),
            ("creation_date", "Criado em"), ("modification_date", "Modificado em"),
            ("password", "Protegido"), ("signatures", "Assinaturas"),
        )
        for key, caption in fields:
            label = QLabel("—")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._labels[key] = label
            form.addRow(f"{caption}:", label)
        scroll.setWidget(content)
        root.addWidget(scroll)

    def set_info(self, info: PDFDocumentInfo | None) -> None:
        if info is None:
            for label in self._labels.values():
                label.setText("—")
            return
        values = {
            "name": info.name,
            "path": str(info.path),
            "size": self._format_size(info.size),
            "page_count": str(info.page_count),
            "title": info.title, "author": info.author, "subject": info.subject,
            "keywords": info.keywords, "creator": info.creator, "producer": info.producer,
            "creation_date": info.creation_date, "modification_date": info.modification_date,
            "password": "Sim" if info.password_protected else "Não",
            "signatures": str(info.signature_count),
        }
        for key, value in values.items():
            self._labels[key].setText(value or "—")

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}"
            value /= 1024
        return "—"
