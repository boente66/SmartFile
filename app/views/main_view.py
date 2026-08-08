from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QToolButton,
    QWidget,
)

from app.views.sidebar_view import SidebarView
from app.views.workspace_view import WorkspaceView
from app.ui.progress_manager import ProgressManager
from app.ui.icon_provider import IconProvider
from app.version import __version__


class MainView(QMainWindow):
    """
    Janela principal do FileConverte.
    Container de todas as funcionalidades.
    """

    version_notification_acknowledged = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_ui()

    # -------------------------
    # Configuração da janela
    # -------------------------
    def _setup_window(self):
        self.setWindowTitle(f"SmartFile {__version__}")
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

    def show_version_notification(self, version: str, message: str) -> None:
        button = getattr(self, "version_notification_button", None)
        if button is None:
            button = QToolButton()
            button.setObjectName("versionNotificationButton")
            self.status.addPermanentWidget(button)
            self.version_notification_button = button
        button.setText(f"Novidades {version}")
        button.setToolTip("Clique para ver as novidades desta versão")

        try:
            button.clicked.disconnect()
        except TypeError:
            pass

        def show_details() -> None:
            QMessageBox.information(
                self, f"SmartFile atualizado para {version}", message,
            )
            self.version_notification_acknowledged.emit(version)
            button.hide()

        button.clicked.connect(show_details)
