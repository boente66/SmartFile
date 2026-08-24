from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class PDFViewerContext:
    """Origem de navegação e ações contextuais do visualizador oficial."""

    kind: str = "DOCUMENT"
    title: str = ""
    protocol_number: str | None = None
    sender_name: str | None = None
    delivery_id: int | None = None
    back_view: str = "documents"
    back_tab: str | None = None
    items: list[tuple[str, Path]] = field(default_factory=list)
    current_item: int = 0
    can_acknowledge: bool = False
    acknowledged: bool = False

    @classmethod
    def document(cls) -> "PDFViewerContext":
        return cls()

