from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CategoryEntity:
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
