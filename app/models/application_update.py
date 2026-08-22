from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ApplicationUpdate:
    version: str
    platform_name: str
    download_url: str
    release_url: str
    asset_name: str | None = None
    notes: str = ""

