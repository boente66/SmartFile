from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.errors.persistence_exceptions import DatabaseError

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 4


def _has_user_tables(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone() is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def _create_legacy_tables(connection: sqlite3.Connection) -> None:
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


def _upgrade_documents(connection: sqlite3.Connection) -> None:
    columns = _columns(connection, "documents")
    additions = {
        "description": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'ACTIVE'",
        "source_path": "TEXT",
        "storage_path": "TEXT",
        "internal_name": "TEXT",
        "managed": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, declaration in additions.items():
        if name not in columns:
            connection.execute(f"ALTER TABLE documents ADD COLUMN {name} {declaration}")
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(name);
        CREATE INDEX IF NOT EXISTS idx_documents_file_type ON documents(file_type);
        CREATE INDEX IF NOT EXISTS idx_documents_checksum ON documents(checksum);
        CREATE INDEX IF NOT EXISTS idx_documents_favorite ON documents(favorite);
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
        CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
        CREATE INDEX IF NOT EXISTS idx_documents_storage_path ON documents(storage_path);
        CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
        """
    )


def migrate(connection: sqlite3.Connection, schema_path: Path) -> int:
    """Cria o schema mínimo ou atualiza bancos legados sem perder documentos."""
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
            return CURRENT_SCHEMA_VERSION

        if current == 0:
            _create_legacy_tables(connection)
            current = 1
        if current < CURRENT_SCHEMA_VERSION:
            _upgrade_documents(connection)
            connection.execute(
                "UPDATE documents SET source_path = path WHERE source_path IS NULL"
            )
            connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            connection.commit()
            logger.info("Banco atualizado para versão %s", CURRENT_SCHEMA_VERSION)
        return CURRENT_SCHEMA_VERSION
    except (sqlite3.Error, OSError) as exc:
        connection.rollback()
        raise DatabaseError(f"Falha ao executar migrations: {exc}") from exc
