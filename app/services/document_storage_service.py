from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.errors.persistence_exceptions import StorageError
from app.models.stored_document import StoredDocument
from app.utils.atomic_output import atomic_output
from app.system.app_paths import AppPaths


class DocumentStorageService:
    """Gerencia arquivos internos sem conhecer banco, Controller ou View."""

    def __init__(self, paths: AppPaths | None = None) -> None:
        self.paths = paths or AppPaths()
        self.paths.ensure_directories()

    def store(self, source_path: Path, checksum: str, cancelled=None) -> StoredDocument:
        source = self._regular_file(source_path, "Arquivo de origem inválido")
        now = datetime.now(timezone.utc)
        internal_name = f"{uuid4()}{source.suffix.lower()}"
        relative = Path(f"{now.year:04d}") / f"{now.month:02d}" / internal_name
        destination = (self.paths.storage / relative).resolve()
        if not self.is_managed_path(destination):
            raise StorageError("Destino recusado fora do storage gerenciado.")
        if destination.exists():
            raise StorageError("Colisão inesperada no nome interno do documento.")

        temporary = self.create_temp_path(source.suffix)
        published = False
        checksum_of = lambda path: self._checksum(path) if cancelled is None else self._checksum(path, cancelled=cancelled)
        try:
            if cancelled is None:
                shutil.copy2(source, temporary)
            else:
                with source.open("rb") as incoming, temporary.open("xb") as outgoing:
                    while chunk := incoming.read(1024*1024):
                        if cancelled():raise InterruptedError("Importação cancelada.")
                        outgoing.write(chunk)
                source_stat = source.stat()
                os.utime(temporary, (source_stat.st_atime, source_stat.st_mtime))
            source_size = source.stat().st_size
            if temporary.stat().st_size != source_size:
                raise StorageError("A cópia temporária possui tamanho divergente.")
            if checksum_of(temporary) != checksum:
                raise StorageError("A cópia temporária falhou na validação SHA-256.")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, destination)
            published = True
            if checksum_of(destination) != checksum:
                raise StorageError("O arquivo armazenado falhou na validação SHA-256.")
            return StoredDocument(
                internal_name=internal_name,
                storage_path=str(destination),
                relative_path=str(relative),
                size=destination.stat().st_size,
            )
        except InterruptedError:
            self._cleanup(temporary, *([destination] if published else []))
            raise
        except StorageError:
            self._cleanup(temporary, destination)
            raise
        except OSError as exc:
            self._cleanup(temporary, destination)
            raise StorageError(f"Não foi possível armazenar o documento: {exc}") from exc

    def exists(self, storage_path: str) -> bool:
        path = Path(storage_path).expanduser().resolve()
        return self.is_managed_path(path) and path.is_file()

    def export(self, storage_path: str, destination: Path) -> Path:
        source = Path(storage_path).expanduser().resolve()
        if not self.is_managed_path(source) or not source.is_file():
            raise StorageError("Arquivo interno inválido para exportação.")
        target = Path(destination).expanduser().absolute()
        if target.exists() and target.is_dir():
            target = target / source.name
        if target.exists():
            raise StorageError(f"O destino já existe: {target}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            checksum = self._checksum(source)
            with atomic_output(target) as temporary:
                shutil.copyfile(source, temporary)
                if self._checksum(temporary) != checksum:
                    raise StorageError("A exportação falhou na validação SHA-256.")
            return target
        except OSError as exc:
            raise StorageError(f"Não foi possível exportar o documento: {exc}") from exc

    def remove(self, storage_path: str) -> None:
        path = Path(storage_path).expanduser().resolve()
        if not self.is_managed_path(path):
            raise StorageError("Remoção recusada fora do storage gerenciado.")
        try:
            if path.exists():
                if not path.is_file():
                    raise StorageError("O caminho gerenciado não é um arquivo regular.")
                path.unlink()
        except OSError as exc:
            raise StorageError(f"Não foi possível remover o arquivo interno: {exc}") from exc

    def is_managed_path(self, path: Path) -> bool:
        candidate = Path(path).expanduser().resolve()
        storage = self.paths.storage.resolve()
        try:
            candidate.relative_to(storage)
            return candidate != storage
        except ValueError:
            return False

    def create_temp_path(self, suffix: str = "") -> Path:
        suffix = suffix if not suffix or suffix.startswith(".") else f".{suffix}"
        return (self.paths.temp / f"{uuid4()}{suffix}.part").resolve()

    @staticmethod
    def _regular_file(path: Path, message: str) -> Path:
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise StorageError(message) from exc
        if not resolved.is_file():
            raise StorageError(message)
        return resolved

    @staticmethod
    def _checksum(path: Path, cancelled=None) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if cancelled and cancelled():raise InterruptedError("Operação de arquivo cancelada.")
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _cleanup(*paths: Path) -> None:
        for path in paths:
            try:
                if path.exists() and path.is_file():
                    path.unlink()
            except OSError:
                pass
