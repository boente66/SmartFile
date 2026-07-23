from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.system.app_paths import AppPaths

_HANDLER_NAME = "smartfile-file"


def configure_logging(data_dir: Path | str | None = None) -> Path:
    """Configura log rotativo local sem registrar credenciais de nuvem."""

    paths = AppPaths(data_dir)
    paths.ensure_directories()
    log_path = paths.logs / "smartfile.log"
    root = logging.getLogger()
    existing = next(
        (
            handler for handler in root.handlers
            if getattr(handler, "name", None) == _HANDLER_NAME
        ),
        None,
    )
    if existing is not None and Path(existing.baseFilename) != log_path:
        root.removeHandler(existing)
        existing.close()
        existing = None
    if existing is None:
        handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=4,
            encoding="utf-8",
        )
        handler.name = _HANDLER_NAME
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    return log_path
