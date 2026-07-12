from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentEntity:
    id: Optional[int] = None
    name: str = ""
    original_name: str = ""
    path: str = ""
    extension: str = ""
    file_type: str = ""
    size: int = 0
    checksum: str = ""
    category: Optional[str] = None
    description: Optional[str] = None
    favorite: bool = False
    status: str = "ACTIVE"
    created_at: str = ""
    updated_at: str = ""
    last_accessed_at: Optional[str] = None
