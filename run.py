from PyQt6.QtWidgets import QApplication
import sys

from app.controllers.auth_controller import AuthController
from app.database.database import Database
from pathlib import Path


# load stylesheet if present
def _load_stylesheet(app: QApplication):
    qss_path = Path(__file__).with_name('assets').joinpath('style.qss')
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))


def main():
    app = QApplication(sys.argv)
    _load_stylesheet(app)

    database = Database()
    controller = AuthController(app, database)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
