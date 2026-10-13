"""Byte-preserving storage. No method updates or removes a canonical artifact."""
import hashlib
import errno
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.validation_locator_service import ValidationLocatorService


@dataclass(frozen=True, slots=True)
class CanonicalValidationArtifact:
    storage_ref: str
    size: int
    sha256: str


class CanonicalArtifactService:
    CHUNK_SIZE = 1024 * 1024

    def __init__(self, paths):
        self.root = paths.data_dir / "validation_artifacts"
        self.root.mkdir(parents=True, exist_ok=True)
        self._safe_path(self.root)
        self.sync_directory(self.root.parent)

    def _safe_path(self, path):
        # Reject symlinks in every component, including the configured root.
        candidate = Path(path).absolute()
        for parent in (candidate, *candidate.parents):
            if parent.is_symlink():
                raise ValueError("Link simbólico recusado no armazenamento canônico.")
        if not candidate.is_relative_to(self.root.absolute()):
            raise ValueError("Referência fora do armazenamento canônico.")
        return candidate

    def path(self, organization_id, storage_ref):
        if not isinstance(storage_ref, str) or not re.fullmatch(
                rf"{int(organization_id)}/SFV1-[A-Za-z0-9_-]{{43}}\.pdf", storage_ref):
            raise ValueError("Referência canônica inválida para a organização.")
        return self._safe_path(self.root / storage_ref)

    @staticmethod
    @contextmanager
    def regular_reader(path):
        path = Path(path)
        if path.is_symlink():
            raise ValueError("Links simbólicos não são arquivos canônicos.")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("Arquivo regular necessário.")
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = None
                yield stream
        finally:
            if descriptor is not None:
                os.close(descriptor)

    @classmethod
    def hash_file(cls, path, cancelled=lambda: False):
        digest = hashlib.sha256()
        size = 0
        with cls.regular_reader(path) as source:
            for block in iter(lambda: source.read(cls.CHUNK_SIZE), b""):
                if cancelled():
                    raise InterruptedError("Verificação cancelada.")
                digest.update(block)
                size += len(block)
        return digest.hexdigest(), size

    @staticmethod
    def sync_directory(path):
        if os.name == "nt":
            return  # Windows file flush remains mandatory; directory fsync is unavailable.
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            try:
                os.fsync(descriptor)
            except OSError as exc:
                if exc.errno not in {errno.EINVAL, errno.ENOTSUP, errno.EBADF}:
                    raise
        finally:
            os.close(descriptor)

    def preserve(self, organization_id, token, source):
        ValidationLocatorService.validate_token(token)
        reference = f"{int(organization_id)}/{token}.pdf"
        destination = self.path(organization_id, reference)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._safe_path(destination.parent)
        self.sync_directory(self.root)
        temporary = destination.with_name(f".{token}.{uuid4().hex}.part")
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
            with os.fdopen(descriptor, "wb") as target, self.regular_reader(source) as original:
                for block in iter(lambda: original.read(self.CHUNK_SIZE), b""):
                    target.write(block)
                target.flush()
                os.fsync(target.fileno())
            digest, size = self.hash_file(temporary)
            if size == 0:
                raise ValueError("Artefato vazio recusado.")
            self._safe_path(destination)
            # Atomic create-if-absent, including concurrent attempts. Windows NTFS
            # supports links too; rename on Windows is a no-overwrite fallback.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                raise ValueError("O artefato canônico já existe; sobrescrita recusada.") from None
            except OSError:
                if os.name != "nt":
                    raise
                os.rename(temporary, destination)
            self.sync_directory(destination.parent)
            if self.hash_file(destination) != (digest, size):
                raise ValueError("Falha na integridade do artefato promovido.")
            return CanonicalValidationArtifact(reference, size, digest)
        finally:
            temporary.unlink(missing_ok=True)

    def checked_path(self, record):
        if not record.artifact_storage_ref:
            raise FileNotFoundError("Artefato não registrado.")
        try:
            path = self.path(record.organization_id, record.artifact_storage_ref)
            digest, size = self.hash_file(path)
        except FileNotFoundError:
            raise FileNotFoundError("Artefato canônico ausente.") from None
        except (OSError, ValueError):
            raise ValueError("Não foi possível verificar o artefato canônico preservado.") from None
        if (digest, size) != (record.final_sha256, record.artifact_size):
            raise ValueError("O arquivo preservado pelo SmartFile não corresponde ao hash registrado.")
        return path

    def export(self, record, destination):
        source = self.checked_path(record)
        target = Path(destination).expanduser().absolute()
        for parent in (target, *target.parents):
            if parent.is_symlink():
                raise ValueError("Destino com link simbólico recusado.")
        target = target.resolve()
        if target.is_relative_to(self.root.parent):
            raise ValueError("Exporte para fora dos dados internos do SmartFile.")
        created = False
        try:
            with self.regular_reader(source) as original, target.open("xb") as output:
                created = True
                for block in iter(lambda: original.read(self.CHUNK_SIZE), b""):
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if self.hash_file(target) != (record.final_sha256, record.artifact_size):
                raise ValueError("A exportação não corresponde ao original registrado.")
            return target
        except Exception:
            if created:
                target.unlink(missing_ok=True)
            raise
