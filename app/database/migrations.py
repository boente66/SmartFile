from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.errors.persistence_exceptions import DatabaseError

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 5


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
        "organization_id": "INTEGER",
        "folder_id": "INTEGER",
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
        CREATE INDEX IF NOT EXISTS idx_documents_organization ON documents(organization_id);
        CREATE INDEX IF NOT EXISTS idx_documents_folder ON documents(folder_id);
        CREATE INDEX IF NOT EXISTS idx_documents_org_checksum ON documents(organization_id, checksum);
        CREATE INDEX IF NOT EXISTS idx_history_document ON history(document_id);
        """
    )


def _upgrade_organizations(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            slug TEXT NOT NULL UNIQUE,
            icon TEXT,
            color TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED'))
        );
        CREATE TABLE IF NOT EXISTS folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            parent_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            color TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'DELETED')),
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (parent_id) REFERENCES folders(id),
            UNIQUE (organization_id, parent_id, name)
        );
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_organizations_status ON organizations(status);
        CREATE INDEX IF NOT EXISTS idx_folders_organization ON folders(organization_id);
        CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders(parent_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_folders_sibling_name
            ON folders(organization_id, COALESCE(parent_id, 0), lower(name))
            WHERE status = 'ACTIVE';
        """
    )
    now = connection.execute("SELECT datetime('now')").fetchone()[0]
    connection.execute(
        """
        INSERT INTO organizations (
            name, description, slug, icon, color, created_at, updated_at, is_default, status
        ) SELECT ?, ?, ?, ?, ?, ?, ?, 1, 'ACTIVE'
        WHERE NOT EXISTS (SELECT 1 FROM organizations)
        """,
        ("Minha Organização", "Organização padrão do SmartFile", "minha-organizacao", "organization", "#2563eb", now, now),
    )
    default_id = connection.execute(
        "SELECT id FROM organizations WHERE status = 'ACTIVE' ORDER BY is_default DESC, id LIMIT 1"
    ).fetchone()[0]
    connection.execute(
        "UPDATE documents SET organization_id = ? WHERE organization_id IS NULL",
        (default_id,),
    )
    connection.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('active_organization_id', ?)",
        (str(default_id),),
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
            _upgrade_organizations(connection)
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
