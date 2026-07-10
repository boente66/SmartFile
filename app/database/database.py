from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path.home() / ".smartfile" / "smartfile.db"
SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class Database:
    """
    Classe base de persistência de dados.
    Equivalente ao Connection/JDBC.
    """

    def __init__(self, db_name: Optional[str] = None):
        self.conn: sqlite3.Connection | None = None
        self.db_name = db_name or str(DEFAULT_DB_PATH)
        self.connect()
        self.create_tables()

    def connect(self) -> sqlite3.Connection:
        if self.conn is None:
            db_path = Path(self.db_name)

            if db_path.parent != Path("."):
                db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(
                self.db_name,
                timeout=30,
                check_same_thread=False,
            )
            self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            self.conn.row_factory = sqlite3.Row

        return self.conn

    def create_tables(self) -> None:
        if not SCHEMA_PATH.exists():
            return

        with self.connect() as conn:
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            conn.executescript(schema_sql)
            conn.commit()
            conn.execute("PRAGMA user_version = 1;")
            conn.commit()

    def execute_query(self, query: str, params: tuple = ()):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return cursor
        except sqlite3.Error as exc:
            print(f"Erro ao executar a consulta: {exc}")
            return None

    def fetch_all(self, query: str, params=None):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                return cursor.fetchall()
        except sqlite3.Error as exc:
            print(f"Erro ao buscar dados: {exc}")
            return []

    def fetch_one(self, query: str, params=None):
        try:
            with self.connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params or ())
                return cursor.fetchone()
        except sqlite3.Error as exc:
            print(f"Erro ao buscar dado: {exc}")
            return None

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None


def get_default_db_path() -> str:
    return str(DEFAULT_DB_PATH)


def initialize_database(db_path: Optional[str] = None) -> str:
    database = Database(db_name=db_path or get_default_db_path())
    return database.db_name


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    database = Database(db_name=db_path or get_default_db_path())
    return database.connect()
