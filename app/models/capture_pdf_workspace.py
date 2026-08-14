from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4


@dataclass(slots=True)
class CapturePdfPage:
    """Página lógica do workspace, independente dos widgets da interface."""

    id: str = field(default_factory=lambda: str(uuid4()))
    source_kind: str = "IMAGE"
    source_path: Path | None = None
    source_page: int | None = None
    image: object | None = None
    rotation: int = 0


@dataclass(slots=True)
class CapturePdfWorkspace:
    """Fonte de verdade da sessão integrada de captura e PDF."""

    pages: list[CapturePdfPage] = field(default_factory=list)
    current_page: int = -1
    source: str | None = None
    dirty: bool = False
    output_name: str = "Novo documento"

    def add_pages(self, pages: list[CapturePdfPage]) -> None:
        if not pages:
            return
        self.pages.extend(pages)
        self.current_page = len(self.pages) - len(pages)
        self.dirty = True

    def snapshot(self) -> list[CapturePdfPage]:
        """Copia a descrição das páginas para uso seguro por workers."""
        return [
            CapturePdfPage(
                id=page.id,
                source_kind=page.source_kind,
                source_path=page.source_path,
                source_page=page.source_page,
                image=page.image.copy() if hasattr(page.image, "copy") else page.image,
                rotation=page.rotation,
            )
            for page in self.pages
        ]

    def remove(self, indexes: list[int]) -> list[CapturePdfPage]:
        selected = sorted({index for index in indexes if 0 <= index < len(self.pages)})
        removed = [self.pages[index] for index in selected]
        for index in reversed(selected):
            self.pages.pop(index)
        self.current_page = min(self.current_page, len(self.pages) - 1)
        if self.pages and self.current_page < 0:
            self.current_page = 0
        self.dirty = self.dirty or bool(removed)
        return removed

    def reorder(self, page_ids: list[str]) -> None:
        if len(page_ids) != len(self.pages) or set(page_ids) != {
            page.id for page in self.pages
        }:
            raise ValueError("A nova ordem não corresponde às páginas do documento.")
        by_id = {page.id: page for page in self.pages}
        current_id = (
            self.pages[self.current_page].id
            if 0 <= self.current_page < len(self.pages) else None
        )
        self.pages = [by_id[page_id] for page_id in page_ids]
        self.current_page = (
            page_ids.index(current_id) if current_id in page_ids else -1
        )
        self.dirty = True

    def rotate(self, indexes: list[int], degrees: int) -> None:
        if degrees % 90:
            raise ValueError("A rotação deve ser múltipla de 90 graus.")
        changed = False
        for index in set(indexes):
            if 0 <= index < len(self.pages):
                self.pages[index].rotation = (
                    self.pages[index].rotation + degrees
                ) % 360
                changed = True
        self.dirty = self.dirty or changed

    def clear(self) -> list[CapturePdfPage]:
        removed = list(self.pages)
        self.pages.clear()
        self.current_page = -1
        self.source = None
        self.dirty = False
        self.output_name = "Novo documento"
        return removed
