from PyQt6.QtWidgets import QApplication
import sys

from app.views.main_view import MainView
from app.controllers.app_controller import AppController


def main():
    app = QApplication(sys.argv)

    main_view = MainView()

    # 🔴 MANTER REFERÊNCIA DO CONTROLLER
    controller = AppController(main_view)
    controller.start()

    main_view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
