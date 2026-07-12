import sqlite3
from pathlib import Path

import pytest

from app.database.database import Database
from app.database.migrations import CURRENT_SCHEMA_VERSION
from app.entities.document_entity import DocumentEntity
from app.repositories.document_repository import DocumentRepository


def _entity(path: Path, checksum: str = "checksum") -> DocumentEntity:
    return DocumentEntity(
        name=path.name,
        original_name=path.name,
        path=str(path),
        extension=path.suffix,
        file_type="PDF",
        size=10,
        checksum=checksum,
        favorite=False,
        status="ACTIVE",
        created_at="2026-07-11 12:00:00",
        updated_at="2026-07-11 12:00:00",
    )


def test_database_creates_document_table_and_required_indexes(tmp_path: Path):
    database = Database(db_name=str(tmp_path / "smartfile.db"))
    connection = database.connect()
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    indexes = {
        row[1] for row in connection.execute("PRAGMA index_list(documents)").fetchall()
    }

    assert "documents" in tables
    assert {
        "idx_documents_name",
        "idx_documents_file_type",
        "idx_documents_checksum",
        "idx_documents_favorite",
        "idx_documents_status",
        "idx_documents_created_at",
    } <= indexes


def test_repository_crud_search_filter_favorite_delete_restore(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    repository = DocumentRepository(str(db_path))
    first = repository.create(_entity(tmp_path / "contrato.pdf", "abc"))
    repository.create(_entity(tmp_path / "relatorio.pdf", "def"))

    assert repository.find_by_id(first.id).name == "contrato.pdf"
    assert len(repository.find_all()) == 2
    assert repository.search("contrato")[0].id == first.id
    assert len(repository.find_by_type("PDF")) == 2
    assert repository.exists_checksum("abc") is True

    favorite = repository.toggle_favorite(first.id)
    assert favorite.favorite is True
    assert repository.find_favorites()[0].id == first.id

    assert repository.soft_delete(first.id) is True
    assert [item.id for item in repository.find_all()] != [first.id]
    assert repository.find_by_id(first.id).status == "TRASHED"

    assert repository.restore(first.id) is True
    assert repository.find_by_id(first.id).status == "ACTIVE"


def test_persistence_survives_close_and_reopen(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    database = Database(db_name=str(db_path))
    repository = DocumentRepository(database=database)
    created = repository.create(_entity(tmp_path / "persistente.pdf"))
    database.close()

    reopened = DocumentRepository(str(db_path))

    assert reopened.find_by_id(created.id).name == "persistente.pdf"


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
        INSERT INTO documents (
            name, original_name, path, extension, file_type, size, checksum,
            created_at, updated_at
        ) VALUES (
            'legado.pdf', 'legado.pdf', '/tmp/legado.pdf', '.pdf', 'PDF', 1,
            'abc', 'now', 'now'
        );
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
    assert {"description", "status"} <= columns


def test_transaction_rolls_back_on_failure(tmp_path: Path):
    database = Database(db_name=str(tmp_path / "smartfile.db"))

    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    name, original_name, path, extension, file_type, size,
                    checksum, created_at, updated_at
                ) VALUES ('x', 'x', '/tmp/x', '.pdf', 'PDF', 1, 'x', 'now', 'now')
                """
            )
            raise RuntimeError("rollback")

    assert database.fetch_one("SELECT * FROM documents WHERE name = 'x'") is None
