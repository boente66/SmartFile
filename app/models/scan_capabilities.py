from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScanCapabilities:
    sources: tuple = ()
    dpi_values: tuple = ()
    color_modes: tuple = ()
    geometry: dict = field(default_factory=dict)
    max_width: float | None = None
    max_height: float | None = None
    unit: str = "UNKNOWN"
    supports_custom_area: bool = False
