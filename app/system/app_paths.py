from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Fonte única dos diretórios de dados utilizados pelo SmartFile."""

    data_dir: Path

    def __init__(self, data_dir: Path | str | None = None) -> None:
        object.__setattr__(
            self,
            "data_dir",
            Path(data_dir).expanduser().resolve() if data_dir else self._default_data_dir(),
        )

    @staticmethod
    def _default_data_dir() -> Path:
        if sys.platform.startswith("win"):
            base = Path(
                os.environ.get(
                    "LOCALAPPDATA",
                    Path.home() / "AppData" / "Local",
                )
            )
        else:
            base = Path(
                os.environ.get(
                    "XDG_DATA_HOME",
                    Path.home() / ".local" / "share",
                )
            )
        return (base / "SmartFile").expanduser().resolve()

    @property
    def database(self) -> Path:
        return self.data_dir / "smartfile.db"

    @property
    def storage(self) -> Path:
        return self.data_dir / "storage"

    @property
    def temp(self) -> Path:
        return self.data_dir / "temp"

    @property
    def thumbnails(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def logs(self) -> Path:
        return self.data_dir / "logs"

    @property
    def backups(self) -> Path:
        return self.data_dir / "backups"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.storage,
            self.temp,
            self.thumbnails,
            self.logs,
            self.backups,
        ):
            path.mkdir(parents=True, exist_ok=True)
