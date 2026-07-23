from PyQt6.QtWidgets import QApplication
import sys

from app.controllers.auth_controller import AuthController
from app.database.database import Database
from app.system.logging_config import configure_logging
from app.system.resources import resource_path


# load stylesheet if present
def _load_stylesheet(app: QApplication):
    qss_path = resource_path("assets/style.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))


def main():
    configure_logging()
    app = QApplication(sys.argv)
    _load_stylesheet(app)

    database = Database()
    controller = AuthController(app, database)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
