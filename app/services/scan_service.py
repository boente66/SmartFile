from PIL import Image
from app.system.system_identification import SystemIdentification


class ScanService:
    """
    Serviço de digitalização real.
    """

    # -------------------------
    # LISTAR DISPOSITIVOS
    # -------------------------
    @staticmethod
    def list_devices() -> list[str]:

        backend = SystemIdentification.get_scanner_backend()

        if backend == "twain":
            try:
                import twain
                sm = twain.SourceManager(0)
                devices = sm.GetSourceList()
                sm.Destroy()
                return devices
            except Exception:
                return []

        elif backend == "sane":
            try:
                import sane
                sane.init()
                devices = [d[0] for d in sane.get_devices()]
                sane.exit()
                return devices
            except Exception:
                return []

        return []

    # -------------------------
    # DIGITALIZAR
    # -------------------------
    @staticmethod
    def scan_page(config):

        backend = SystemIdentification.get_scanner_backend()

        if backend == "twain":
            return ScanService._scan_windows(config)

        elif backend == "sane":
            return ScanService._scan_linux(config)

        raise RuntimeError("Sistema não suportado")

    # -------------------------
    # WINDOWS
    # -------------------------
    @staticmethod
    def _scan_windows(config):

        import twain
        import win32ui

        sm = twain.SourceManager(0)
        source = sm.OpenSource(config.device_name)

        source.SetCapability(
            twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, config.dpi
        )

        source.SetCapability(
            twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, config.dpi
        )

        source.RequestAcquire(0, 0)
        handle, _ = source.XferImageNatively()

        source.CloseSource()
        sm.Destroy()

        if not handle:
            raise RuntimeError("Falha ao digitalizar")

        bmp = win32ui.CreateBitmapFromHandle(handle)

        img = Image.frombuffer(
            "RGB",
            (bmp.GetInfo()["bmWidth"], bmp.GetInfo()["bmHeight"]),
            bmp.GetBitmapBits(True),
            "raw",
            "BGRX",
            0,
            1
        )

        return img

    # -------------------------
    # LINUX
    # -------------------------
    @staticmethod
    def _scan_linux(config):

        import sane

        sane.init()
        dev = sane.open(config.device_name)

        dev.resolution = config.dpi
        dev.mode = {
            "color": "Color",
            "gray": "Gray",
            "bw": "Lineart"
        }[config.color_mode]

        dev.start()
        img = dev.snap()

        dev.close()
        sane.exit()

        return img