from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TagEntity:
    id: Optional[int] = None
    name: str = ""
    created_at: Optional[str] = None
