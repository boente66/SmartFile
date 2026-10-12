from io import BytesIO

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
                with twain.SourceManager(0) as manager:
                    getter = getattr(manager, "get_source_list", None)
                    if getter is None:
                        getter = manager.GetSourceList
                    return list(getter() or [])
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
        if SystemIdentification.get_scanner_backend() == "twain":
            return [(ScanService._source_label(value),value) for value in ScanService.capabilities(device_name).sources]
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

        with twain.SourceManager(0) as manager:
            opener = getattr(manager, "open_source", None)
            source = (
                opener(config.device_name)
                if opener is not None
                else manager.OpenSource(config.device_name)
            )
            if source is None:
                raise RuntimeError("O scanner selecionado não está disponível.")
            try:
                setter = getattr(source, "set_capability", None) or getattr(source, "SetCapability", None)
                if setter:
                    for capability in ("ICAP_XRESOLUTION", "ICAP_YRESOLUTION"):
                        if hasattr(twain, capability): setter(getattr(twain, capability), twain.TWTY_FIX32, config.dpi)
                    if hasattr(twain, "ICAP_PIXELTYPE"):
                        pixel_type = {"color": "TWPT_RGB", "gray": "TWPT_GRAY", "bw": "TWPT_BW"}[config.color_mode]
                        setter(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, getattr(twain, pixel_type))
                if config.source_name and setter and hasattr(twain,"CAP_FEEDERENABLED"):
                    feeder=any(term in config.source_name.lower() for term in ("adf","feeder","duplex"))
                    setter(twain.CAP_FEEDERENABLED,twain.TWTY_BOOL,feeder)
                request = getattr(source, "request_acquire", None)
                if request is not None:
                    request(show_ui=False, modal_ui=False)
                    loop = getattr(source,"modal_loop",None)
                    if loop:loop()
                    info = ScanService._twain_info(source)
                    handle, _remaining = source.xfer_image_natively()
                    bitmap = twain.dib_to_bm_file(handle)
                    with Image.open(BytesIO(bitmap), formats=["BMP"]) as image:
                        return ScanService._twain_image(image, config, info)

                source.SetCapability(
                    twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, config.dpi
                )
                source.SetCapability(
                    twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, config.dpi
                )
                source.RequestAcquire(0, 0)
                loop=getattr(source,"ModalLoop",None)
                if loop:loop()
                info = ScanService._twain_info(source)
                handle, _remaining = source.XferImageNatively()
                if not handle:
                    raise RuntimeError("Falha ao digitalizar.")
                bitmap = twain.DIBToBMFile(handle)
                if isinstance(bitmap, (bytes, bytearray)):
                    with Image.open(BytesIO(bitmap), formats=["BMP"]) as image:
                        return ScanService._twain_image(image, config, info)
                raise RuntimeError("O backend TWAIN não retornou uma imagem compatível.")
            finally:
                closer = getattr(source, "close", None)
                if closer is not None:
                    closer()
                elif hasattr(source, "CloseSource"):
                    source.CloseSource()

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
            # Read back effective resolution; requested values are not measurements.
            effective = None
            area = None
            try:
                options = {item[1]: item for item in dev.get_options() if len(item) > 8}
                resolution = options.get("resolution")
                if resolution and resolution[5] == getattr(sane, "UNIT_DPI", 4):
                    effective = float(dev.resolution)
                names = ("tl-x", "tl-y", "br-x", "br-y")
                if all(name in options and options[name][5] == getattr(sane,"UNIT_MM",3) for name in names):
                    values = [float(getattr(dev,name.replace("-","_"))) for name in names]
                    width,height = values[2]-values[0],values[3]-values[1]
                    if width>0 and height>0: area=(width,height)
            except (AttributeError, TypeError, ValueError): pass
            dev.start()
            image = dev.snap()
            image.info["requested_dpi"] = config.dpi
            if effective: image.info["effective_dpi"] = (effective, effective)
            if area and effective:
                # Only use physical area if delivered pixels corroborate backend geometry.
                if all(abs(p*25.4/effective-mm)/mm < .025 for p,mm in zip(image.size,area)):
                    image.info["physical_area_mm"] = area
            return image
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
    def _twain_info(source):
        try:
            getter=getattr(source,"GetImageInfo",None)
            return getter() if getter else getattr(source,"image_info",{})
        except Exception:return {}

    @staticmethod
    def _twain_image(image, config, info=None):
        result = image.convert("RGB")
        result.info["requested_dpi"] = config.dpi
        # TW_IMAGEINFO reports the delivered X/Y resolution, independent of requested DPI.
        info = info or {}
        dpi = (info.get("XResolution",0),info.get("YResolution",0))
        if dpi and all(25 <= value <= 9600 for value in dpi):
            result.info["effective_dpi"] = dpi
        return result

    @staticmethod
    def capabilities(device_name):
        from app.models.scan_capabilities import ScanCapabilities
        if SystemIdentification.get_scanner_backend() == "twain":
            return ScanService._twain_capabilities(device_name)
        if SystemIdentification.get_scanner_backend() != "sane": return ScanCapabilities()
        import sane
        device = None
        try:
            sane.init(); device = sane.open(device_name)
            options = {item[1]: item for item in device.get_options() if len(item) > 8}
            geometry = {name: {"unit": item[5], "constraints": item[8]}
                        for name, item in options.items()
                        if name in {"tl-x", "tl-y", "br-x", "br-y", "page-width", "page-height"}}
            def maximum(name):
                item=options.get(name)
                if not item or item[5]!=getattr(sane,"UNIT_MM",3):return None
                constraint=item[8]
                if isinstance(constraint,(list,tuple)) and len(constraint)>=2:return float(constraint[1])
                return None
            return ScanCapabilities(
                max_width=maximum("page-width") or maximum("br-x"),
                max_height=maximum("page-height") or maximum("br-y"),
                sources=tuple(options.get("source", (None,)*9)[8] or ()),
                dpi_values=tuple(options.get("resolution", (None,)*9)[8] or ()),
                color_modes=tuple(options.get("mode", (None,)*9)[8] or ()),
                geometry=geometry, supports_custom_area=all(name in geometry for name in ("tl-x","tl-y","br-x","br-y")),
                unit="MM" if geometry and all(v["unit"] == getattr(sane, "UNIT_MM", 3) for v in geometry.values()) else "UNKNOWN")
        except Exception: return ScanCapabilities()
        finally:
            if device is not None:
                try:device.close()
                except Exception:pass
            try:sane.exit()
            except Exception:pass

    @staticmethod
    def _twain_capabilities(device_name):
        from app.models.scan_capabilities import ScanCapabilities
        import twain
        source=None
        try:
            with twain.SourceManager(0) as manager:
                opener=getattr(manager,"open_source",None) or manager.OpenSource
                source=opener(device_name)
                getter=getattr(source,"get_capability",None) or getattr(source,"GetCapability",None)
                def values(name):
                    if not getter or not hasattr(twain,name):return ()
                    try:
                        raw=getter(getattr(twain,name))
                        raw=raw[1] if isinstance(raw,tuple) and len(raw)==2 else raw
                        if isinstance(raw,dict):return (raw.get("MinValue"),raw.get("MaxValue"))
                        if isinstance(raw,tuple) and len(raw)==3 and isinstance(raw[2],(tuple,list)):return tuple(raw[2])
                        return tuple(raw) if isinstance(raw,(tuple,list)) else (raw,)
                    except Exception:return ()
                feeder=values("CAP_FEEDERENABLED")
                sources=("Flatbed", "ADF") if True in feeder else ("Flatbed",)
                dpi=values("ICAP_XRESOLUTION")
                modes=tuple(name for name,constant in (("color","TWPT_RGB"),("gray","TWPT_GRAY"),("bw","TWPT_BW"))
                            if getattr(twain,constant,None) in values("ICAP_PIXELTYPE"))
                result=ScanCapabilities(sources=sources,dpi_values=dpi,color_modes=modes)
                closer=getattr(source,"close",None) or getattr(source,"CloseSource",None)
                if closer:closer()
                source=None
                return result
        except Exception:return ScanCapabilities()
        finally:
            if source is not None:
                closer=getattr(source,"close",None) or getattr(source,"CloseSource",None)
                if closer:
                    try:closer()
                    except Exception:pass

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
