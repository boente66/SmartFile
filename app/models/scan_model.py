# app/models/scan_model.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ScanPage:
    """
    Representa uma página digitalizada.
    """
    image_path: Path


@dataclass
class ScanModel:
    """
    Mantém estado da sessão de digitalização.
    """

    device_name: str | None = None
    dpi: int = 300
    color_mode: str = "Color"

    pages: List[ScanPage] = field(default_factory=list)

    # -------------------------
    # PÁGINAS
    # -------------------------

    def add_page(self, image_path: Path):
        """
        Adiciona página digitalizada.
        """
        self.pages.append(ScanPage(image_path))

    def remove_page(self, index: int):
        """
        Remove página pelo índice.
        """
        if 0 <= index < len(self.pages):
            self.pages.pop(index)

    def clear_pages(self):
        """
        Limpa sessão de digitalização.
        """
        self.pages.clear()

    # -------------------------
    # CONSULTAS
    # -------------------------

    def page_count(self) -> int:
        return len(self.pages)

    def has_pages(self) -> bool:
        return len(self.pages) > 0

    def get_image_paths(self) -> List[Path]:
        """
        Retorna caminhos das imagens.
        """
        return [page.image_path for page in self.pages]