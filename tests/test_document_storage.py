from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from uuid import UUID

import pytest

from app.entities.document_entity import DocumentEntity
from app.errors.persistence_exceptions import DuplicateDocumentError, StorageError
from app.services.document_service import DocumentService
from app.services.document_storage_service import DocumentStorageService
from app.system.app_paths import AppPaths


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_app_paths_creates_complete_structure(tmp_path: Path):
    paths = AppPaths(tmp_path / "SmartFile")
    paths.ensure_directories()

    assert paths.database == paths.data_dir / "smartfile.db"
    assert all(
        path.is_dir()
        for path in (
            paths.storage, paths.temp, paths.thumbnails, paths.logs, paths.backups
        )
    )


def test_import_copies_and_validates_managed_document(tmp_path: Path):
    source = tmp_path / "origem" / "contrato.pdf"
    source.parent.mkdir()
    source.write_bytes(b"conteudo-do-contrato")
    service = DocumentService(db_path=str(tmp_path / "dados" / "smartfile.db"))

    document = service.import_document(str(source))
    stored = Path(document.storage_path)

    assert source.read_bytes() == b"conteudo-do-contrato"
    assert stored.is_file()
    assert stored.read_bytes() == source.read_bytes()
    assert _checksum(stored) == _checksum(source) == document.checksum
    assert len(stored.parent.name) == 2 and stored.parent.name.isdigit()
    assert len(stored.parent.parent.name) == 4 and stored.parent.parent.name.isdigit()
    UUID(Path(document.internal_name).stem)
    assert document.path == document.storage_path
    assert document.managed is True

    persisted = service.document_repository.find_by_id(document.id)
    assert persisted.storage_path == str(stored)
    assert persisted.source_path == str(source.resolve())


def test_original_can_be_moved_or_deleted_without_breaking_open(tmp_path: Path):
    source = tmp_path / "origem.pdf"
    source.write_bytes(b"independente")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    document = service.import_document(str(source))

    moved = tmp_path / "movido.pdf"
    source.replace(moved)
    assert service.open_document(document.id).storage_path == document.storage_path
    moved.unlink()
    assert service.open_document(document.id).managed is True


def test_duplicate_does_not_create_second_copy(tmp_path: Path):
    first = tmp_path / "primeiro.pdf"
    second = tmp_path / "segundo.pdf"
    first.write_bytes(b"duplicado")
    second.write_bytes(b"duplicado")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    service.import_document(str(first))
    before = list(service.database.paths.storage.rglob("*.*"))

    with pytest.raises(DuplicateDocumentError):
        service.import_document(str(second))

    assert list(service.database.paths.storage.rglob("*.*")) == before
    assert len(service.list_documents()) == 1


def test_soft_delete_keeps_physical_file(tmp_path: Path):
    source = tmp_path / "documento.pdf"
    source.write_bytes(b"lixeira")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    document = service.import_document(str(source))

    assert service.delete_document(document.id) is True

    assert Path(document.storage_path).is_file()
    assert service.document_repository.find_by_id(document.id).status == "TRASHED"


def test_copy_error_leaves_no_file_or_database_record(tmp_path: Path, monkeypatch):
    source = tmp_path / "falha.pdf"
    source.write_bytes(b"falha")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))

    def fail_copy(*_args, **_kwargs):
        raise OSError("falha simulada")

    monkeypatch.setattr(shutil, "copy2", fail_copy)
    with pytest.raises(StorageError):
        service.import_document(str(source))

    assert service.document_repository.find_all() == []
    assert list(service.database.paths.storage.rglob("*.*")) == []
    assert list(service.database.paths.temp.glob("*")) == []


def test_checksum_mismatch_removes_temporary_and_final_files(tmp_path: Path):
    paths = AppPaths(tmp_path / "SmartFile")
    storage = DocumentStorageService(paths)
    source = tmp_path / "invalido.pdf"
    source.write_bytes(b"conteudo")

    with pytest.raises(StorageError):
        storage.store(source, "checksum-incorreto")

    assert list(paths.storage.rglob("*.*")) == []
    assert list(paths.temp.glob("*")) == []


def test_repository_failure_removes_stored_file(tmp_path: Path, monkeypatch):
    source = tmp_path / "rollback.pdf"
    source.write_bytes(b"rollback")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))

    def fail_create(_entity):
        raise RuntimeError("banco indisponível")

    monkeypatch.setattr(service.document_repository, "create", fail_create)
    with pytest.raises(RuntimeError):
        service.import_document(str(source))

    assert list(service.database.paths.storage.rglob("*.*")) == []


def test_path_traversal_is_rejected_and_export_is_valid(tmp_path: Path):
    paths = AppPaths(tmp_path / "SmartFile")
    storage = DocumentStorageService(paths)
    source = tmp_path / "fonte.pdf"
    source.write_bytes(b"exportavel")
    stored = storage.store(source, _checksum(source))

    assert storage.is_managed_path(Path(stored.storage_path)) is True
    assert storage.is_managed_path(paths.storage / ".." / "fora.pdf") is False
    with pytest.raises(StorageError):
        storage.remove(str(paths.storage / ".." / "fora.pdf"))

    exported = storage.export(stored.storage_path, tmp_path / "exportado.pdf")
    assert exported.read_bytes() == source.read_bytes()


def test_legacy_record_remains_readable(tmp_path: Path):
    legacy_file = tmp_path / "legado.pdf"
    legacy_file.write_bytes(b"legado")
    service = DocumentService(db_path=str(tmp_path / "smartfile.db"))
    now = service._now()
    entity = service.document_repository.create(
        DocumentEntity(
            name=legacy_file.name,
            original_name=legacy_file.name,
            path=str(legacy_file),
            extension=".pdf",
            file_type="PDF",
            size=legacy_file.stat().st_size,
            checksum=_checksum(legacy_file),
            managed=False,
            created_at=now,
            updated_at=now,
        )
    )

    opened = service.open_document(entity.id)

    assert opened.path == str(legacy_file)
    assert opened.storage_path is None
    assert opened.managed is False
