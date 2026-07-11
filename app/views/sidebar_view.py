from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QSizePolicy
)
from PyQt6.QtCore import pyqtSignal as Signal, Qt


class SidebarView(QWidget):
    """
    Sidebar principal da aplicação.
    Apenas emite sinais indicando a ferramenta selecionada.
    """

    tool_selected = Signal(str)

    def __init__(self):
        super().__init__()

        self._buttons = {}

        self._setup_ui()

    # -------------------------
    # UI setup
    # -------------------------
    def _setup_ui(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("SmartFile")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        title.setStyleSheet("font-weight:bold;font-size:18px;")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)

        subtitle = QLabel("Mini GED")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle.setObjectName("sidebarSubtitle")
        layout.addWidget(subtitle)

        section = QLabel("FERRAMENTAS")
        section.setAlignment(Qt.AlignmentFlag.AlignLeft)
        section.setObjectName("sidebarSection")
        layout.addWidget(section)

        self._add_button(layout, "Documentos", "documents")
        self._add_button(layout, "Converter", "converter")
        self._add_button(layout, "PDF Tools", "pdf")
        self._add_button(layout, "Scanner", "scanner")

        layout.addStretch()

    # -------------------------
    # Helpers
    # -------------------------
    def _add_button(self, layout, text: str, tool_name: str):

        button = QPushButton(text)
        button.setObjectName("sidebarButton")

        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        button.clicked.connect(
            lambda: self._on_button_clicked(tool_name)
        )

        layout.addWidget(button)

        self._buttons[tool_name] = button

    def _on_button_clicked(self, tool_name: str):

        self.set_active_tool(tool_name)

        self.tool_selected.emit(tool_name)

    # -------------------------
    # Highlight ativo
    # -------------------------
    def set_active_tool(self, tool_name: str):

        for name, button in self._buttons.items():

            if name == tool_name:
                button.setProperty("selected", True)
            else:
                button.setProperty("selected", False)

        for button in self._buttons.values():
            button.style().unpolish(button)
            button.style().polish(button)
