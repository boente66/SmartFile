from pathlib import Path

from app.database.base_persistence import BasePersistence
from app.services.document_service import DocumentService
from app.services.history_service import HistoryService


def test_import_list_search_and_favorite(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))

    source = tmp_path / "relatorio.pdf"
    source.write_bytes(b"pdf-content")

    document = service.import_document(str(source))

    assert document.name == "relatorio.pdf"
    assert document.path == str(source)
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


def test_history_service_tracks_document_actions(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    service = DocumentService(db_path=str(db_path))
    history_service = HistoryService(db_path=str(db_path))

    source = tmp_path / "historico.pdf"
    source.write_bytes(b"historico")

    document = service.import_document(str(source))
    history = history_service.list_history(document.id)

    assert len(history) >= 1
    assert history[0].action == "import"


def test_base_persistence_initializes_database(tmp_path: Path):
    db_path = tmp_path / "smartfile.db"
    persistence = BasePersistence(db_path=str(db_path))

    with persistence.get_connection() as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('documents', 'history')"
        ).fetchall()

    assert len(tables) == 2
