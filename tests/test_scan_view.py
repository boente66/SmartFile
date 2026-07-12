import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication

from app.views.scan_view import ScanView

_APPLICATION: QApplication | None = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def test_scan_view_exposes_supported_configuration_and_page_state():
    _app()
    view = ScanView()
    view.set_devices(["Scanner de teste"])
    view.profile_combo.setCurrentIndex(2)
    view.dpi_combo.setCurrentIndex(1)

    config = view.get_scan_config()

    assert config == {
        "device": "Scanner de teste",
        "dpi": 300,
        "color": "bw",
        "source": None,
    }
    assert view.btn_save.isEnabled() is False

    pixmap = QPixmap(200, 300)
    pixmap.fill()
    view.add_thumbnail(pixmap)

    assert view.page_list.count() == 1
    assert view.pages_title.text() == "Páginas digitalizadas (1)"
    assert view.page_indicator.text() == "Página 1 de 1"
    assert view.btn_save.isEnabled() is True

    view.remove_thumbnail(0)
    assert view.page_list.count() == 0
    assert view.btn_save.isEnabled() is False
    view.close()


def test_scan_view_prefers_flatbed_and_preserves_backend_value():
    _app()
    view = ScanView()
    view.set_sources([
        ("Alimentador automático (ADF)", "ADF"),
        ("Mesa de vidro", "Flatbed"),
    ])

    assert view.source_combo.isEnabled() is True
    assert view.source_combo.currentText() == "Mesa de vidro"
    assert view.get_scan_config()["source"] == "Flatbed"
    view.close()


def test_scan_view_disables_capture_without_devices():
    _app()
    view = ScanView()

    view.set_devices([])

    assert view.device_combo.isEnabled() is False
    assert view.btn_scan.isEnabled() is False
    assert view.btn_scan_more.isEnabled() is False
    view.close()
