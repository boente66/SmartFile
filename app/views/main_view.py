from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QStatusBar
)

from app.views.sidebar_view import SidebarView
from app.views.workspace_view import WorkspaceView
from app.ui.progress_manager import ProgressManager


class MainView(QMainWindow):
    """
    Janela principal do FileConverte.
    Container de todas as funcionalidades.
    """

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_ui()

    # -------------------------
    # Configuração da janela
    # -------------------------
    def _setup_window(self):
        self.setWindowTitle("FileConverte")
        self.resize(1200, 800)

    # -------------------------
    # UI principal
    # -------------------------
    def _setup_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Sidebar
        self.sidebar = SidebarView()
        self.sidebar.setFixedWidth(220)

        # Workspace
        self.workspace = WorkspaceView()

        layout.addWidget(self.sidebar)
        layout.addWidget(self.workspace, 1)

        # Status bar
        self.status = QStatusBar()
        self.status.showMessage("Pronto")
        self.setStatusBar(self.status)

        # Progress manager
        self.progress = ProgressManager(self.status)
