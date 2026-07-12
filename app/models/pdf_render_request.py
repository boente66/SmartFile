from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PDFRenderRequest:
    path: Path
    page_number: int
    zoom: float = 1.0
    rotation: int = 0
    password: str | None = None
    highlights: tuple[tuple[float, float, float, float], ...] = ()

    def validate(self) -> None:
        if self.page_number < 1:
            raise ValueError("Número de página inválido.")
        if not 0.25 <= self.zoom <= 4.0:
            raise ValueError("Zoom fora dos limites permitidos.")
        if self.rotation % 90:
            raise ValueError("A rotação deve ser múltipla de 90 graus.")
