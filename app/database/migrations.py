from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.errors.persistence_exceptions import DatabaseError

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = 7


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
        "cloud_status": "TEXT NOT NULL DEFAULT 'LOCAL_ONLY'",
        "cloud_provider": "TEXT",
        "remote_id": "TEXT",
        "remote_version": "TEXT",
        "last_synced_at": "TEXT",
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
        CREATE INDEX IF NOT EXISTS idx_documents_cloud_status ON documents(cloud_status);
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


def _upgrade_cloud(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS cloud_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL CHECK (provider IN ('ONEDRIVE', 'GOOGLE_DRIVE')),
            email TEXT,
            display_name TEXT,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            expires_at TEXT,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cloud_settings (
            organization_id INTEGER PRIMARY KEY,
            cloud_account_id INTEGER,
            sync_mode TEXT NOT NULL DEFAULT 'LOCAL',
            remote_root_id TEXT,
            last_sync TEXT,
            delta_token TEXT,
            paused INTEGER NOT NULL DEFAULT 0 CHECK (paused IN (0, 1)),
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (cloud_account_id) REFERENCES cloud_accounts(id)
        );
        CREATE TABLE IF NOT EXISTS sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            operation TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status, created_at);
        CREATE INDEX IF NOT EXISTS idx_sync_jobs_document ON sync_jobs(document_id);
        CREATE INDEX IF NOT EXISTS idx_cloud_accounts_provider ON cloud_accounts(provider, status);
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO cloud_settings (organization_id, sync_mode, paused)
        SELECT id, 'LOCAL', 0 FROM organizations
        """
    )


def _upgrade_auth(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            email TEXT UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL,
            phone TEXT,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
            is_superuser INTEGER NOT NULL DEFAULT 0 CHECK (is_superuser IN (0, 1)),
            failed_login_attempts INTEGER NOT NULL DEFAULT 0,
            locked_until TEXT,
            last_login_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT,
            last_activity_at TEXT,
            revoked_at TEXT,
            device_name TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS organization_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('OWNER', 'ADMIN', 'EDITOR', 'VIEWER')),
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (organization_id) REFERENCES organizations(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (organization_id, user_id)
        );
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id, revoked_at);
        CREATE INDEX IF NOT EXISTS idx_members_user ON organization_members(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_members_organization ON organization_members(organization_id, status);
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
            _upgrade_organizations(connection)
            _upgrade_cloud(connection)
            _upgrade_auth(connection)
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
