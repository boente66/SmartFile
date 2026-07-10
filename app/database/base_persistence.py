from __future__ import annotations

import sqlite3
from typing import Optional

from app.database.database import Database


class BasePersistence(Database):
    """Compat shim for older imports expecting a BasePersistence-style API."""

    def __init__(self, db_path: Optional[str] = None):
        super().__init__(db_name=db_path)

    def get_connection(self) -> sqlite3.Connection:
        return self.connect()
