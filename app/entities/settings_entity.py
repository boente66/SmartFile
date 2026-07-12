from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SettingsEntity:
    key: str = ""
    value: str = ""
    updated_at: Optional[str] = None
