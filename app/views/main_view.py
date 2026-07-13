from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QStatusBar
    ,QToolButton
)

from app.views.sidebar_view import SidebarView
from app.views.workspace_view import WorkspaceView
from app.ui.progress_manager import ProgressManager
from app.ui.icon_provider import IconProvider


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
        self.setWindowTitle("SmartFile")
        self.setWindowIcon(IconProvider.icon("app"))
        self.resize(1100, 700)
        self.setMinimumSize(800, 560)

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
        self.sidebar.setFixedWidth(200)
        self.sidebar.setObjectName("sidebar")

        # Workspace
        self.workspace = WorkspaceView()
        self.workspace.setObjectName("workspace")

        layout.addWidget(self.sidebar)
        layout.addWidget(self.workspace, 1)

        # Status bar
        self.status = QStatusBar()
        self.status.showMessage("Pronto")
        self.setStatusBar(self.status)

        # Progress manager
        self.progress = ProgressManager(self.status)
        self.account_button = QToolButton()
        self.account_button.setObjectName("accountButton")
        self.account_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.status.addPermanentWidget(self.account_button)

    def set_account(self, display_name: str, menu) -> None:
        self.account_button.setText(display_name)
        self.account_button.setMenu(menu)
