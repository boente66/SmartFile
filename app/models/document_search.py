from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DocumentSearchFilters:
    file_type: str | None = None
    category: str | None = None
    source_type: str | None = None
    period_days: int | None = None
    favorite: bool | None = None
    cloud_status: str | None = None

    @property
    def active(self) -> bool:
        return any(
            value not in (None, "", "Todos", "Todas")
            for value in (
                self.file_type, self.category, self.source_type,
                self.period_days, self.favorite, self.cloud_status,
            )
        )
