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

    @staticmethod
    def list_sources(device_name: str) -> list[tuple[str, str]]:
        """Retorna fontes SANE reais sem manter o dispositivo aberto."""
        if SystemIdentification.get_scanner_backend() != "sane":
            return []
        import sane

        device = None
        try:
            sane.init()
            device = sane.open(device_name)
            option = next(
                (item for item in device.get_options() if len(item) > 8 and item[1] == "source"),
                None,
            )
            if option is None:
                return []
            constraint = option[8]
            values = list(constraint) if isinstance(constraint, (list, tuple)) else []
            return [(ScanService._source_label(str(value)), str(value)) for value in values]
        except Exception:
            return []
        finally:
            if device is not None:
                try:
                    device.close()
                except Exception:
                    pass
            try:
                sane.exit()
            except Exception:
                pass

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

        dev = None
        try:
            sane.init()
            dev = sane.open(config.device_name)
            if config.source_name and hasattr(dev, "source"):
                dev.source = config.source_name
            dev.resolution = config.dpi
            dev.mode = {
                "color": "Color",
                "gray": "Gray",
                "bw": "Lineart"
            }[config.color_mode]
            dev.start()
            return dev.snap()
        finally:
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
            try:
                sane.exit()
            except Exception:
                pass

    @staticmethod
    def friendly_error(error: Exception, source_name: str | None = None) -> str:
        message = str(error).strip()
        normalized = message.lower()
        if "feeder out of documents" in normalized or "document feeder" in normalized:
            source = (source_name or "").lower()
            if "flatbed" in source or "platen" in source:
                return (
                    "O scanner informou que o alimentador automático está sem folhas, mesmo com a mesa "
                    "selecionada. Atualize os dispositivos e confirme a fonte no scanner."
                )
            return (
                "O alimentador automático (ADF) está sem folhas. Coloque o documento no alimentador "
                "ou selecione ‘Mesa de vidro’ em Fonte de papel."
            )
        if "device busy" in normalized or "busy" == normalized:
            return "O scanner está ocupado. Aguarde alguns segundos e tente novamente."
        if "cover open" in normalized:
            return "A tampa do scanner está aberta. Feche-a e tente novamente."
        if "paper jam" in normalized or "jammed" in normalized:
            return "Há papel preso no scanner. Remova-o e tente novamente."
        if "cancelled" in normalized or "canceled" in normalized:
            return "A digitalização foi cancelada."
        return message or "Não foi possível digitalizar o documento."

    @staticmethod
    def _source_label(value: str) -> str:
        normalized = value.lower()
        if "flatbed" in normalized or "platen" in normalized:
            return "Mesa de vidro"
        if "duplex" in normalized:
            return "Alimentador automático (frente e verso)"
        if "adf" in normalized or "feeder" in normalized:
            return "Alimentador automático (ADF)"
        return value
