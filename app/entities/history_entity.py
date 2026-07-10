from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class HistoryEntity:
    id: Optional[int] = None
    document_id: Optional[int] = None
    action: str = ""
    description: Optional[str] = None
    created_at: Optional[str] = None
