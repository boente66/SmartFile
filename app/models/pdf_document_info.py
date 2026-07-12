from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PDFDocumentInfo:
    path: Path
    name: str
    size: int
    page_count: int
    page_width: float
    page_height: float
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""
    password_protected: bool = False
    signature_count: int = 0

    @property
    def has_signatures(self) -> bool:
        return self.signature_count > 0
