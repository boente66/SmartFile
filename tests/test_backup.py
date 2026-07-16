import hashlib
import json
import sqlite3
import zipfile
from types import SimpleNamespace

import pytest

from app.database.database import Database
from app.errors.backup_exceptions import (
    BackupPermissionError,
    InvalidBackupDestinationError,
)
from app.services.backup_service import BackupService


class _Context:
    def __init__(self, administrator: bool):
        self.current_user = SimpleNamespace(id=None, is_superuser=administrator)

    def is_system_admin(self):
        return self.current_user.is_superuser


def test_system_administrator_creates_consistent_full_zip(tmp_path):
    database = Database(str(tmp_path / "data" / "smartfile.db"))
    document = database.storage_dir / "aa" / "documento.pdf"
    document.parent.mkdir(parents=True)
    document.write_bytes(b"documento importante")
    avatar = database.data_dir / "avatars" / "perfil.png"
    avatar.parent.mkdir()
    avatar.write_bytes(b"avatar")
    (database.data_dir / ".cloud_tokens.key").write_text("nao-incluir")
    (database.paths.logs / "smartfile.log").write_text("nao-incluir")
    progress = []

    result = BackupService(database, _Context(True)).create_full_backup(
        tmp_path / "backup.zip", lambda value, message: progress.append((value, message))
    )

    assert result.output_path.is_file()
    assert result.sha256 == hashlib.sha256(result.output_path.read_bytes()).hexdigest()
    assert progress[-1] == (100, "Backup concluído")
    with zipfile.ZipFile(result.output_path) as archive:
        names = set(archive.namelist())
        assert names == {
            "database/smartfile.db",
            "storage/aa/documento.pdf",
            "avatars/perfil.png",
            "manifest.json",
        }
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["scope"] == "FULL_SYSTEM"
        assert manifest["format_version"] == 1
        assert "oauth_tokens" in manifest["excludes"]
        for item in manifest["files"]:
            assert hashlib.sha256(archive.read(item["path"])).hexdigest() == item["sha256"]
        extracted = tmp_path / "snapshot.db"
        extracted.write_bytes(archive.read("database/smartfile.db"))
    with sqlite3.connect(extracted) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    actions = {
        row["action"] for row in database.fetch_all(
            "SELECT action FROM audit_log WHERE action LIKE 'BACKUP_%'"
        )
    }
    assert actions == {"BACKUP_STARTED", "BACKUP_CREATED"}
    database.close()


def test_common_user_cannot_create_backup(tmp_path):
    database = Database(str(tmp_path / "data" / "smartfile.db"))
    with pytest.raises(BackupPermissionError):
        BackupService(database, _Context(False)).create_full_backup(tmp_path / "backup.zip")
    assert not (tmp_path / "backup.zip").exists()
    database.close()


@pytest.mark.parametrize("name", ["backup.tar", "backup"])
def test_backup_requires_zip_extension(tmp_path, name):
    database = Database(str(tmp_path / "data" / "smartfile.db"))
    with pytest.raises(InvalidBackupDestinationError):
        BackupService(database, _Context(True)).create_full_backup(tmp_path / name)
    database.close()


def test_backup_cannot_be_written_inside_managed_storage(tmp_path):
    database = Database(str(tmp_path / "data" / "smartfile.db"))
    with pytest.raises(InvalidBackupDestinationError):
        BackupService(database, _Context(True)).create_full_backup(
            database.storage_dir / "backup.zip"
        )
    database.close()
