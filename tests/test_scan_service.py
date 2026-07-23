import sys
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from app.models.scan_config_model import ScanConfigModel
from app.services.scan_service import ScanService
from app.system.system_identification import SystemIdentification
from app.workers.scan_worker import ScanWorker


class _FakeDevice:
    def __init__(self):
        self.source = "ADF"
        self.resolution = None
        self.mode = None
        self.closed = False
        self.started = False

    def get_options(self):
        return [(0, "source", "Source", "", 0, 0, 0, 0, ("ADF", "ADF Duplex", "Flatbed"))]

    def start(self):
        self.started = True

    def snap(self):
        return Image.new("RGB", (10, 10), "white")

    def close(self):
        self.closed = True


def _fake_sane(device):
    return SimpleNamespace(
        init=lambda: None,
        exit=lambda: None,
        open=lambda _name: device,
    )


def test_sane_sources_are_discovered_and_translated(monkeypatch):
    device = _FakeDevice()
    monkeypatch.setitem(sys.modules, "sane", _fake_sane(device))
    monkeypatch.setattr(SystemIdentification, "get_scanner_backend", lambda: "sane")

    sources = ScanService.list_sources("escl:test")

    assert sources == [
        ("Alimentador automático (ADF)", "ADF"),
        ("Alimentador automático (frente e verso)", "ADF Duplex"),
        ("Mesa de vidro", "Flatbed"),
    ]
    assert device.closed is True


def test_linux_scan_applies_selected_flatbed_source(monkeypatch):
    device = _FakeDevice()
    monkeypatch.setitem(sys.modules, "sane", _fake_sane(device))
    config = ScanConfigModel("escl:test", dpi=300, color_mode="color", source_name="Flatbed")

    image = ScanService._scan_linux(config)

    assert device.source == "Flatbed"
    assert device.resolution == 300
    assert device.mode == "Color"
    assert device.started is True and device.closed is True
    image.close()


def test_feeder_error_is_presented_in_portuguese():
    message = ScanService.friendly_error(RuntimeError("Document feeder out of documents"), "ADF")

    assert "sem folhas" in message
    assert "Mesa de vidro" in message
    assert "Document feeder" not in message


def test_scan_worker_keeps_native_finished_signal():
    assert "finished" not in ScanWorker.__dict__


def test_windows_pytwain_devices_are_discovered(monkeypatch):
    class Manager:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        @staticmethod
        def get_source_list():
            return ["Scanner TWAIN x64"]

    monkeypatch.setitem(
        sys.modules,
        "twain",
        SimpleNamespace(SourceManager=lambda _window: Manager()),
    )
    monkeypatch.setattr(SystemIdentification, "get_scanner_backend", lambda: "twain")

    assert ScanService.list_devices() == ["Scanner TWAIN x64"]


def test_windows_pytwain_scan_returns_detached_rgb_image(monkeypatch):
    buffer = BytesIO()
    Image.new("RGB", (4, 3), "white").save(buffer, format="BMP")

    class Source:
        def __init__(self):
            self.closed = False

        def request_acquire(self, **_kwargs):
            return None

        @staticmethod
        def xfer_image_natively():
            return 123, 0

        def close(self):
            self.closed = True

    source = Source()

    class Manager:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        @staticmethod
        def open_source(_name):
            return source

    monkeypatch.setitem(
        sys.modules,
        "twain",
        SimpleNamespace(
            SourceManager=lambda _window: Manager(),
            dib_to_bm_file=lambda _handle: buffer.getvalue(),
        ),
    )
    config = ScanConfigModel("Scanner TWAIN x64", dpi=300, color_mode="color")

    image = ScanService._scan_windows(config)

    assert image.mode == "RGB"
    assert image.size == (4, 3)
    assert source.closed is True
    image.close()
