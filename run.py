from PyQt6.QtWidgets import QApplication
import sys
from tempfile import TemporaryDirectory

from app.controllers.auth_controller import AuthController
from app.database.database import Database
from app.system.app_paths import AppPaths
from app.system.logging_config import configure_logging
from app.system.resources import resource_path
from app.version import __version__


# load stylesheet if present
def _load_stylesheet(app: QApplication):
    qss_path = resource_path("assets/style.qss")
    if qss_path.exists():
        app.setStyleSheet(qss_path.read_text(encoding='utf-8'))


def _configure_application_identity(app: QApplication) -> None:
    """Expõe ao desktop Linux a identidade usada pelo launcher XDG."""

    app.setApplicationName("SmartFile")
    app.setApplicationDisplayName("SmartFile")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("SmartFile")
    app.setDesktopFileName("smartfile")


def smoke_test() -> int:
    """Valida o bundle sem abrir uma janela ou tocar nos dados reais do usuário."""

    app = QApplication.instance() or QApplication(["SmartFile", "--smoke-test"])
    _configure_application_identity(app)
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
                resource_path("assets/sounds/request_alert.wav"),
            )
            if not all(path.is_file() for path in required):
                return 2
            if not all((AppController, DocumentController, PDFController, MainView)):
                return 3
            if not paths.database.is_file():
                return 4
            # Exercise native libraries and local assistance in the frozen bundle.
            from PIL import Image, ImageDraw
            from app.services.document_geometry_service import DocumentGeometryService
            from app.services.signature_verification_service import SignatureVerificationService
            from PyQt6.QtMultimedia import QSoundEffect
            image = Image.new("RGB", (160, 220), "black")
            ImageDraw.Draw(image).rectangle((20, 20, 140, 200), fill="white")
            geometry = DocumentGeometryService.detect(image)
            image.close()
            if geometry.detection_status != "DETECTED": return 5
            if not SignatureVerificationService.qr_png("https://validar.iti.gov.br/"): return 6
            if QSoundEffect is None: return 7
            app.processEvents()
            return 0
        finally:
            database.close()


def main():
    if "--smoke-test" in sys.argv:
        raise SystemExit(smoke_test())
    configure_logging()
    app = QApplication(sys.argv)
    _configure_application_identity(app)
    _load_stylesheet(app)

    database = Database()
    controller = AuthController(app, database)
    controller.start()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
