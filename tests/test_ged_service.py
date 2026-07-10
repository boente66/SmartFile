from pathlib import Path

from app.services.ged_service import delete_document, list_documents, rename_document


def test_list_documents_filters_and_collects_metadata(tmp_path: Path):
    docs_dir = tmp_path / "ged"
    docs_dir.mkdir()

    (docs_dir / "relatorio.pdf").write_bytes(b"pdf")
    (docs_dir / "foto.jpg").write_bytes(b"jpg")
    (docs_dir / "anotacoes.txt").write_bytes(b"txt")
    (docs_dir / "subdir").mkdir()
    (docs_dir / "subdir" / "contrato.docx").write_bytes(b"docx")

    items = list_documents(docs_dir, search="rel")

    assert len(items) == 1
    assert items[0]["name"] == "relatorio.pdf"
    assert items[0]["extension"].lower() == ".pdf"


def test_rename_and_delete_document(tmp_path: Path):
    docs_dir = tmp_path / "ged"
    docs_dir.mkdir()

    file_path = docs_dir / "draft.txt"
    file_path.write_text("draft")

    renamed = rename_document(file_path, "final.txt")
    assert renamed.exists()
    assert renamed.name == "final.txt"

    delete_document(renamed)
    assert not renamed.exists()
