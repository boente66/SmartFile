from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Sequence

from app.database.migrations import migrate
from app.errors.persistence_exceptions import DatabaseError
from app.system.app_paths import AppPaths
from app.system.resources import resource_path

logger = logging.getLogger(__name__)
SCHEMA_PATH = resource_path("app/database/schema.sql")


DEFAULT_DB_PATH = AppPaths().database


class Database:
    """Gerencia conexão, transações e evolução do schema SQLite."""

    def __init__(self, db_name: Optional[str] = None):
        self.db_path = Path(db_name).expanduser() if db_name else DEFAULT_DB_PATH
        self.paths = AppPaths(self.db_path.parent)
        self.paths.ensure_directories()
        self.db_name = str(self.db_path)
        self.conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self.connect()
        self.create_tables()

    @property
    def data_dir(self) -> Path:
        return self.paths.data_dir

    @property
    def storage_dir(self) -> Path:
        return self.paths.storage

    @property
    def temp_dir(self) -> Path:
        return self.paths.temp

    def connect(self) -> sqlite3.Connection:
        with self._lock:
            if self.conn is None:
                try:
                    self.db_path.parent.mkdir(parents=True, exist_ok=True)
                    self.conn = sqlite3.connect(
                        self.db_name,
                        timeout=30,
                        check_same_thread=False,
                        isolation_level=None,
                    )
                    self.conn.row_factory = sqlite3.Row
                    self.conn.execute("PRAGMA foreign_keys = ON")
                    self.conn.execute("PRAGMA journal_mode = WAL")
                    self.conn.execute("PRAGMA synchronous = NORMAL")
                    self.conn.execute("PRAGMA busy_timeout = 30000")
                    logger.info("Banco conectado: %s", self.db_path)
                except (sqlite3.Error, OSError) as exc:
                    raise DatabaseError(f"Não foi possível abrir o banco: {exc}") from exc
            return self.conn

    def create_tables(self) -> None:
        migrate(self.connect(), SCHEMA_PATH)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        with self._lock:
            nested = connection.in_transaction
            savepoint = f"smartfile_{id(threading.current_thread())}"
            try:
                connection.execute(f"SAVEPOINT {savepoint}" if nested else "BEGIN IMMEDIATE")
                yield connection
                connection.execute(f"RELEASE SAVEPOINT {savepoint}" if nested else "COMMIT")
            except Exception:
                if connection.in_transaction:
                    connection.execute(
                        f"ROLLBACK TO SAVEPOINT {savepoint}" if nested else "ROLLBACK"
                    )
                    if nested:
                        connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise

    def execute_query(self, query: str, params: Sequence[object] = ()) -> sqlite3.Cursor:
        try:
            with self.transaction() as connection:
                return connection.execute(query, tuple(params))
        except sqlite3.Error as exc:
            raise DatabaseError(f"Falha ao executar consulta: {exc}") from exc

    def fetch_all(self, query: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        try:
            return self.connect().execute(query, tuple(params)).fetchall()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Falha ao consultar dados: {exc}") from exc

    def fetch_one(self, query: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        try:
            return self.connect().execute(query, tuple(params)).fetchone()
        except sqlite3.Error as exc:
            raise DatabaseError(f"Falha ao consultar dado: {exc}") from exc

    def close(self) -> None:
        with self._lock:
            if self.conn is not None:
                self.conn.close()
                self.conn = None
                logger.info("Banco fechado: %s", self.db_path)

    def backup_to(self, destination: Path | str) -> Path:
        """Cria um snapshot SQLite consistente sem copiar WAL parcialmente."""

        target_path = Path(destination).expanduser().resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target: sqlite3.Connection | None = None
        try:
            with self._lock:
                target = sqlite3.connect(str(target_path))
                self.connect().backup(target)
                target.commit()
            return target_path
        except (sqlite3.Error, OSError) as exc:
            target_path.unlink(missing_ok=True)
            raise DatabaseError(f"Não foi possível criar o snapshot do banco: {exc}") from exc
        finally:
            if target is not None:
                target.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *_args) -> None:
        self.close()


def get_default_db_path() -> str:
    return str(DEFAULT_DB_PATH)


def initialize_database(db_path: Optional[str] = None) -> str:
    database = Database(db_name=db_path or get_default_db_path())
    return database.db_name


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    return Database(db_name=db_path or get_default_db_path()).connect()
