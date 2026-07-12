from __future__ import annotations

import sqlite3
from typing import Optional, Sequence

from app.database.database import Database
from app.errors.persistence_exceptions import RepositoryError


class BaseRepository:
    """Infraestrutura comum para repositories baseados em sqlite3."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        database: Database | None = None,
    ) -> None:
        self.database = database or Database(db_name=db_path)

    def connect(self) -> sqlite3.Connection:
        """Mantém compatibilidade com consumidores existentes."""
        return self.database.connect()

    def _write(self, query: str, params: Sequence[object] = ()) -> sqlite3.Cursor:
        connection = self.connect()
        try:
            if connection.in_transaction:
                return connection.execute(query, tuple(params))
            with self.database.transaction() as transaction:
                return transaction.execute(query, tuple(params))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Falha ao persistir dados: {exc}") from exc

    def _fetch_one(self, query: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        try:
            return self.connect().execute(query, tuple(params)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Falha ao consultar dado: {exc}") from exc

    def _fetch_all(self, query: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        try:
            return self.connect().execute(query, tuple(params)).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Falha ao consultar dados: {exc}") from exc
