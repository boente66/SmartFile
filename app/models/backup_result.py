from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackupResult:
    output_path: Path
    size: int
    sha256: str
    file_count: int
    created_at: str
