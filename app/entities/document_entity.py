from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentEntity:
    id: Optional[int] = None
    name: str = ""
    original_name: Optional[str] = None
    path: str = ""
    file_type: Optional[str] = None
    extension: Optional[str] = None
    size: Optional[int] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    favorite: int = 0
    checksum: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_accessed_at: Optional[str] = None
