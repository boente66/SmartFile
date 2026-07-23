from PyQt6.QtWidgets import QApplication
import sys
from tempfile import TemporaryDirectory

from app.controllers.auth_controller import AuthController
from app.database.database import Database
from app.system.app_paths import AppPaths
from app.system.logging_config import configure_logging
from app.system.resources import resource_path


# load stylesheet if present
def _load_stylesheet(app: QApplication):
    qss_path = resource_path("assets/style.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))


def smoke_test() -> int:
    """Valida o bundle sem abrir uma janela ou tocar nos dados reais do usuário."""

    app = QApplication.instance() or QApplication(["SmartFile", "--smoke-test"])
    with TemporaryDirectory(prefix="smartfile-smoke-") as directory:
        paths = AppPaths(directory)
        paths.ensure_directories()
        database = Database(str(paths.database))
        try:
            from app.controllers.app_controller import AppController
            from app.controllers.document_controller import DocumentController
            from app.controllers.pdf_controller import PDFController
            from app.views.main_view import MainView

            required = (
                resource_path("assets/style.qss"),
                resource_path("assets/icons/app.svg"),
                resource_path("app/database/schema.sql"),
            )
            if not all(path.is_file() for path in required):
                return 2
            if not all((AppController, DocumentController, PDFController, MainView)):
                return 3
            if not paths.database.is_file():
                return 4
            app.processEvents()
            return 0
        finally:
            database.close()


def main():
    if "--smoke-test" in sys.argv:
        raise SystemExit(smoke_test())
    configure_logging()
    app = QApplication(sys.argv)
    _load_stylesheet(app)

    database = Database()
    controller = AuthController(app, database)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
