import sqlite3
from pathlib import Path

import pytest

from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.entities.category_entity import CategoryEntity
from app.entities.settings_entity import SettingsEntity
from app.entities.tag_entity import TagEntity
from app.repositories.category_repository import CategoryRepository
from app.repositories.settings_repository import SettingsRepository
from app.repositories.tag_repository import TagRepository


def test_legacy_database_is_migrated_without_losing_documents(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            original_name TEXT, path TEXT NOT NULL, file_type TEXT,
            extension TEXT, size INTEGER, category TEXT, tags TEXT,
            favorite INTEGER DEFAULT 0, checksum TEXT, created_at TEXT,
            updated_at TEXT, last_accessed_at TEXT
        );
        CREATE TABLE history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER,
            action TEXT NOT NULL, description TEXT, created_at TEXT NOT NULL
        );
        INSERT INTO documents (name, path) VALUES ('legado.pdf', '/tmp/legado.pdf');
        PRAGMA user_version = 1;
        """
    )
    connection.commit()
    connection.close()

    database = Database(db_name=str(db_path))
    migrated = database.connect()

    assert migrated.execute("PRAGMA user_version").fetchone()[0] == CURRENT_SCHEMA_VERSION
    assert migrated.execute("SELECT name FROM documents").fetchone()[0] == "legado.pdf"
    columns = {row[1] for row in migrated.execute("PRAGMA table_info(documents)")}
    assert {"internal_name", "category_id", "status"} <= columns


def test_transaction_rolls_back_on_failure(tmp_path: Path):
    database = Database(db_name=str(tmp_path / "smartfile.db"))

    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            connection.execute(
                "INSERT INTO settings (key, value, updated_at) VALUES ('theme', 'dark', 'now')"
            )
            raise RuntimeError("rollback")

    assert database.fetch_one("SELECT * FROM settings WHERE key = 'theme'") is None


def test_specialized_repositories_share_database(tmp_path: Path):
    database = Database(db_name=str(tmp_path / "smartfile.db"))
    categories = CategoryRepository(database=database)
    tags = TagRepository(database=database)
    settings = SettingsRepository(database=database)

    category = categories.create(
        CategoryEntity(name="Contratos", created_at="now", updated_at="now")
    )
    tag = tags.create(TagEntity(name="cliente", created_at="now"))
    settings.set(SettingsEntity(key="theme", value="light", updated_at="now"))

    assert categories.find_by_id(category.id).name == "Contratos"
    assert tags.find_by_id(tag.id).name == "cliente"
    assert settings.find_by_key("theme").value == "light"
