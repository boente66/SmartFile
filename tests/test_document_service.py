from pathlib import Path

import pytest

from app.database.database import Database
from app.errors.persistence_exceptions import DuplicateDocumentError
from app.services.document_service import DocumentService
from app.services.history_service import HistoryService


def test_import_list_search_and_favorite(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))

    source = tmp_path / "relatorio.pdf"
    source.write_bytes(b"pdf-content")

    document = service.import_document(str(source))

    assert document.name == "relatorio.pdf"
    assert Path(document.path).parent == tmp_path / "storage"
    assert Path(document.path).exists()
    assert document.internal_name == Path(document.path).name
    assert document.favorite is False

    documents = service.list_documents()
    assert len(documents) == 1

    search_results = service.search_documents("rel")
    assert len(search_results) == 1

    service.toggle_favorite(document.id)
    favorite_documents = service.filter_by_type("PDF")
    assert favorite_documents[0].favorite is True


def test_delete_and_recent_documents(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))

    first = tmp_path / "primeiro.txt"
    first.write_text("primeiro")
    second = tmp_path / "segundo.pdf"
    second.write_text("segundo")

    service.import_document(str(first))
    service.import_document(str(second))

    deleted = service.delete_document(1)
    assert deleted is True

    recent_documents = service.get_recent_documents()
    assert len(recent_documents) == 1
    assert recent_documents[0].name == "segundo.pdf"

    restored = service.restore_document(1)
    assert restored.status == "ACTIVE"
    assert len(service.list_documents()) == 2


def test_history_service_tracks_document_actions(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))
    history_service = HistoryService(db_path=str(db_path))

    source = tmp_path / "historico.pdf"
    source.write_bytes(b"historico")

    document = service.import_document(str(source))
    history = history_service.list_history(document.id)

    assert len(history) >= 1
    assert history[0].action == "IMPORT"


def test_database_initializes_schema(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    database = Database(db_name=str(db_path))

    with database.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    assert {"documents", "history", "categories", "tags", "settings"} <= tables


def test_docx_is_classified_with_the_official_type(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))
    source = tmp_path / "contrato.docx"
    source.write_bytes(b"docx-content")

    document = service.import_document(str(source))

    assert document.file_type == "DOCX"
    assert service.filter_by_type("DOCX")[0].id == document.id


def test_duplicate_content_is_rejected_by_sha256(tmp_path: Path):
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"same-content")
    second.write_bytes(b"same-content")
    service.import_document(str(first))

    with pytest.raises(DuplicateDocumentError):
        service.import_document(str(second))
