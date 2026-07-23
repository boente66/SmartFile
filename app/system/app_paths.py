from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Fonte única dos diretórios de dados utilizados pelo SmartFile."""

    data_dir: Path
    config_dir: Path

    def __init__(
        self,
        data_dir: Path | str | None = None,
        config_dir: Path | str | None = None,
    ) -> None:
        resolved_data = (
            Path(data_dir).expanduser().resolve()
            if data_dir
            else self._default_data_dir()
        )
        object.__setattr__(
            self,
            "data_dir",
            resolved_data,
        )
        object.__setattr__(
            self,
            "config_dir",
            (
                Path(config_dir).expanduser().resolve()
                if config_dir
                else resolved_data if data_dir else self._default_config_dir()
            ),
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

    @staticmethod
    def _default_config_dir() -> Path:
        if sys.platform.startswith("win"):
            base = Path(
                os.environ.get(
                    "APPDATA",
                    Path.home() / "AppData" / "Roaming",
                )
            )
            return (base / "SmartFile").expanduser().resolve()
        # Preserva o layout Linux já publicado.
        return AppPaths._default_data_dir()

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

    @property
    def config(self) -> Path:
        return self.config_dir

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.config_dir,
            self.storage,
            self.temp,
            self.thumbnails,
            self.logs,
            self.backups,
        ):
            path.mkdir(parents=True, exist_ok=True)
