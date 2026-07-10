from PyQt6.QtWidgets import QApplication
import sys

from app.views.main_view import MainView
from app.controllers.app_controller import AppController
from pathlib import Path


# load stylesheet if present
def _load_stylesheet(app: QApplication):
    qss_path = Path(__file__).with_name('assets').joinpath('style.qss')
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))


def main():
    app = QApplication(sys.argv)
    _load_stylesheet(app)

    main_view = MainView()

    # 🔴 MANTER REFERÊNCIA DO CONTROLLER
    controller = AppController(main_view)
    controller.start()

    main_view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
