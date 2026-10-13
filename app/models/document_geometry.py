"""Immutable geometry in source-image coordinates; no UI dependencies."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentGeometryResult:
    corners: tuple
    normalized_corners: tuple
    pixel_width: float
    pixel_height: float
    physical_width_mm: float | None = None
    physical_height_mm: float | None = None
    standard_size: str = "CUSTOM"
    orientation: str = "SQUARE_OR_UNDETERMINED"
    skew_degrees: float = 0.0
    perspective_detected: bool = False
    confidence: float = 0.0
    detection_status: str = "NOT_DETECTED"
    measurement_source: str = "UNKNOWN"
    possible_clipping: bool = False
    analysis_resolution: tuple = (0, 0)
    detection_ms: float = 0.0
    boundary_status: str = "UNKNOWN"
    boundary_evidence: tuple = ()

    @property
    def reliable_measurement(self):
        return (self.measurement_source in {"DEVICE_GEOMETRY", "SCANNER_DPI", "CALIBRATED"}
                and self.confidence >= .8 and not self.possible_clipping
                and self.physical_width_mm is not None and self.physical_height_mm is not None
                and 10 <= self.physical_width_mm <= 1000
                and 10 <= self.physical_height_mm <= 1000)

    def description(self):
        name = {"CUSTOM": "Personalizado", "LETTER": "Carta"}.get(self.standard_size, self.standard_size)
        orientation = {"PORTRAIT": "Retrato", "LANDSCAPE": "Paisagem"}.get(self.orientation, "Orientação indeterminada")
        size = ""
        if self.physical_width_mm is not None:
            prefix = "≈ " if self.measurement_source == "ESTIMATED" else ""
            size = f" · {prefix}{self.physical_width_mm:.1f} × {self.physical_height_mm:.1f} mm"
        state = "✓ Folha detectada" if self.detection_status == "DETECTED" and self.confidence >= .8 else "! Revisar enquadramento"
        if self.detection_status == "MANUAL": state = "Enquadramento definido manualmente"
        if self.detection_status == "NOT_DETECTED": state = "? Não foi possível determinar a folha"
        if self.possible_clipping: state = "! Possível documento cortado pelo scanner"
        return f"{name}{size} · {orientation}\n{state}"
