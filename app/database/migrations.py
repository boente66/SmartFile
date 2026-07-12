from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.errors.persistence_exceptions import DatabaseError

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Migration:
    version: int
    apply: Callable[[sqlite3.Connection], None]


def _has_user_tables(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone()
    return row is not None


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _migration_1(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            original_name TEXT, path TEXT NOT NULL, file_type TEXT,
            extension TEXT, size INTEGER, category TEXT, tags TEXT,
            favorite INTEGER DEFAULT 0, checksum TEXT, created_at TEXT,
            updated_at TEXT, last_accessed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER,
            action TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL
        );
        """
    )


def _migration_2(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            description TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        """
    )
    columns = _column_names(connection, "documents")
    additions = {
        "internal_name": "TEXT",
        "category_id": "INTEGER REFERENCES categories(id) ON DELETE SET NULL",
        "status": "TEXT NOT NULL DEFAULT 'ACTIVE'",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE documents ADD COLUMN {name} {declaration}")
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);
        CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
        """
    )


MIGRATIONS = (Migration(1, _migration_1), Migration(2, _migration_2))


def migrate(connection: sqlite3.Connection, schema_path: Path) -> int:
    """Atualiza um banco novo ou existente de forma incremental."""
    try:
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > CURRENT_SCHEMA_VERSION:
            raise DatabaseError(
                f"Banco versão {current} é mais novo que a aplicação ({CURRENT_SCHEMA_VERSION})."
            )
        if current == 0 and not _has_user_tables(connection):
            connection.executescript(schema_path.read_text(encoding="utf-8"))
            connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            connection.commit()
            logger.info("Schema inicializado na versão %s", CURRENT_SCHEMA_VERSION)
            return CURRENT_SCHEMA_VERSION

        for migration in MIGRATIONS:
            if migration.version <= current:
                continue
            migration.apply(connection)
            connection.execute(f"PRAGMA user_version = {migration.version}")
            connection.commit()
            current = migration.version
            logger.info("Migration %s aplicada", migration.version)
        return current
    except (sqlite3.Error, OSError) as exc:
        connection.rollback()
        raise DatabaseError(f"Falha ao executar migrations: {exc}") from exc
