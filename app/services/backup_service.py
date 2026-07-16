"""Backup administrativo completo e portátil em formato ZIP."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable
from uuid import uuid4

from app.errors.backup_exceptions import (
    BackupPermissionError,
    BackupStorageError,
    InvalidBackupDestinationError,
)
from app.models.backup_result import BackupResult
from app.services.audit_service import AuditService
from app.version import __version__

logger = logging.getLogger(__name__)
ProgressCallback = Callable[[int, str], None]


class BackupService:
    """Cria snapshot do banco e copia somente dados necessários ao restauro."""

    FORMAT_VERSION = 1
    CHUNK_SIZE = 1024 * 1024

    def __init__(self, database, session_context):
        self.database = database
        self.context = session_context
        self.audit = AuditService(database)

    def create_full_backup(
        self,
        destination: Path | str,
        progress: ProgressCallback | None = None,
    ) -> BackupResult:
        self._require_system_administrator()
        output = self._validate_destination(destination)
        temporary_output = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
        created_at = datetime.now(timezone.utc).isoformat()
        user_id = getattr(getattr(self.context, "current_user", None), "id", None)
        self.audit.record(
            "BACKUP_STARTED",
            user_id=user_id,
            target_type="system_backup",
            description=f"Backup administrativo iniciado: {output.name}",
        )
        self._progress(progress, 5, "Preparando snapshot do banco")

        try:
            with tempfile.TemporaryDirectory(
                prefix="smartfile-backup-", dir=self.database.temp_dir
            ) as temporary_directory:
                snapshot = Path(temporary_directory) / "smartfile.db"
                self.database.backup_to(snapshot)
                sources = [(snapshot, "database/smartfile.db")]
                sources.extend(self._tree_files(self.database.storage_dir, "storage"))
                sources.extend(self._tree_files(self.database.data_dir / "avatars", "avatars"))
                manifest_files = self._write_zip(
                    temporary_output, sources, created_at, progress
                )

            os.replace(temporary_output, output)
            checksum = self._sha256(output)
            result = BackupResult(
                output_path=output,
                size=output.stat().st_size,
                sha256=checksum,
                file_count=len(manifest_files),
                created_at=created_at,
            )
            self.audit.record(
                "BACKUP_CREATED",
                user_id=user_id,
                target_type="system_backup",
                description=(
                    f"Backup administrativo concluído: {output.name} "
                    f"({result.file_count} arquivos)"
                ),
            )
            logger.info(
                "Backup administrativo concluído output=%s files=%s size=%s",
                output,
                result.file_count,
                result.size,
            )
            self._progress(progress, 100, "Backup concluído")
            return result
        except Exception as exc:
            temporary_output.unlink(missing_ok=True)
            if isinstance(
                exc,
                (BackupPermissionError, InvalidBackupDestinationError, BackupStorageError),
            ):
                raise
            logger.exception("Falha ao criar backup administrativo em %s", output)
            raise BackupStorageError(
                "Não foi possível concluir o backup ZIP. Nenhum arquivo parcial foi mantido."
            ) from exc

    def _write_zip(
        self,
        output: Path,
        sources: list[tuple[Path, str]],
        created_at: str,
        progress: ProgressCallback | None,
    ) -> list[dict[str, object]]:
        manifest_files: list[dict[str, object]] = []
        total = max(len(sources), 1)
        with zipfile.ZipFile(
            output,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for index, (source, archive_name) in enumerate(sources, start=1):
                checksum = self._sha256(source)
                archive.write(source, archive_name)
                manifest_files.append(
                    {
                        "path": archive_name,
                        "size": source.stat().st_size,
                        "sha256": checksum,
                    }
                )
                value = 10 + int((index / total) * 80)
                self._progress(progress, value, f"Adicionando {archive_name}")

            manifest = {
                "format": "SmartFile Administrative Backup",
                "format_version": self.FORMAT_VERSION,
                "smartfile_version": __version__,
                "created_at": created_at,
                "scope": "FULL_SYSTEM",
                "contains": ["database", "storage", "avatars"],
                "excludes": [
                    "oauth_tokens",
                    "oauth_configuration",
                    "logs",
                    "cache",
                    "temporary_files",
                    "previous_backups",
                ],
                "files": manifest_files,
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )
        return manifest_files

    @staticmethod
    def _tree_files(root: Path, archive_root: str) -> Iterable[tuple[Path, str]]:
        if not root.exists():
            return []
        resolved_root = root.resolve()
        files: list[tuple[Path, str]] = []
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise BackupStorageError(
                    f"O backup foi cancelado porque há um link simbólico em {archive_root}."
                )
            if not path.is_file():
                continue
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(resolved_root)
            except ValueError as exc:
                raise BackupStorageError("Arquivo fora do diretório gerenciado.") from exc
            files.append((resolved, (Path(archive_root) / relative).as_posix()))
        return files

    def _validate_destination(self, destination: Path | str) -> Path:
        output = Path(destination).expanduser()
        if output.suffix.lower() != ".zip":
            raise InvalidBackupDestinationError("O backup deve possuir extensão .zip.")
        try:
            output = output.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise InvalidBackupDestinationError(
                "Não foi possível acessar a pasta escolhida para o backup."
            ) from exc
        if output.exists() and not output.is_file():
            raise InvalidBackupDestinationError("O destino do backup não é um arquivo válido.")
        for managed_directory in (
            self.database.storage_dir,
            self.database.data_dir / "avatars",
            self.database.temp_dir,
        ):
            managed = managed_directory.resolve()
            if output == managed or managed in output.parents:
                raise InvalidBackupDestinationError(
                    "Escolha uma pasta fora do storage, dos avatares e dos temporários."
                )
        return output

    def _require_system_administrator(self) -> None:
        if not self.context or not self.context.is_system_admin():
            raise BackupPermissionError(
                "Somente o administrador do sistema pode criar um backup completo."
            )

    @classmethod
    def _sha256(cls, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(cls.CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _progress(callback: ProgressCallback | None, value: int, message: str) -> None:
        if callback:
            callback(value, message)
