from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from uuid import uuid4

from app.errors.transport_exceptions import (
    TransportCancelledError,
    TransportConfigurationError,
    TransportIntegrityError,
    TransportRetryableError,
)
from app.transport.transport_adapter import TransportAdapter
from app.transport.transport_models import TransportResult, TransportUploadRequest


class NASTransportAdapter(TransportAdapter):
    """Transporte para caminho NAS previamente montado ou acessível pelo SO."""

    CHUNK_SIZE = 1024 * 1024

    def __init__(self, endpoint: str, organization_segment: str):
        self.endpoint = endpoint.strip()
        if not self.endpoint:
            raise TransportConfigurationError("Destino NAS não configurado.")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", organization_segment):
            raise TransportConfigurationError("Identificador da organização inválido.")
        self.organization_segment = organization_segment

    def test_connection(self) -> TransportResult:
        temporary: Path | None = None
        try:
            endpoint = self._endpoint_root(require_existing=True)
            if not endpoint.is_dir():
                return TransportResult(False, "O destino NAS não é um diretório.")
            with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".smartfile-write-test-", dir=endpoint,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(b"SmartFile")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.unlink()
            temporary = None
            return TransportResult(True, "Conectado. O destino NAS permite escrita.")
        except (TransportConfigurationError, TransportRetryableError) as exc:
            return TransportResult(False, str(exc))
        except PermissionError:
            return TransportResult(False, "Sem permissão de escrita no destino NAS.")
        except OSError:
            return TransportResult(False, "Destino NAS indisponível.")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def upload(self, request: TransportUploadRequest) -> TransportResult:
        source = self._local_file(request.local_path)
        root = self._documents_root(create=True)
        remote_name = self._safe_remote_name(request.remote_name)
        destination = self._inside_root(root / remote_name, root)
        temporary = self._inside_root(
            root / f".{remote_name}.{uuid4().hex}.part", root,
        )
        transferred = 0
        total = source.stat().st_size
        try:
            with source.open("rb") as reader, temporary.open("xb") as writer:
                while True:
                    if request.cancellation_requested and request.cancellation_requested():
                        raise TransportCancelledError("Transferência NAS cancelada.")
                    chunk = reader.read(self.CHUNK_SIZE)
                    if not chunk:
                        break
                    writer.write(chunk)
                    transferred += len(chunk)
                    if request.progress_callback:
                        request.progress_callback(transferred, total)
                writer.flush()
                os.fsync(writer.fileno())
            checksum = self._checksum(temporary)
            if checksum != request.expected_checksum:
                raise TransportIntegrityError(
                    "A cópia temporária no NAS falhou na validação SHA-256."
                )
            if request.cancellation_requested and request.cancellation_requested():
                raise TransportCancelledError("Transferência NAS cancelada.")
            os.replace(temporary, destination)
            final_checksum = self._checksum(destination)
            if final_checksum != request.expected_checksum:
                destination.unlink(missing_ok=True)
                raise TransportIntegrityError(
                    "O documento no NAS falhou na validação SHA-256."
                )
            return TransportResult(
                True, "Documento enviado ao NAS.", str(destination),
                final_checksum, transferred,
            )
        except (TransportCancelledError, TransportIntegrityError):
            temporary.unlink(missing_ok=True)
            raise
        except (PermissionError, OSError) as exc:
            temporary.unlink(missing_ok=True)
            raise TransportRetryableError(
                "Destino NAS temporariamente indisponível ou sem permissão."
            ) from exc

    def delete(self, remote_path: str) -> TransportResult:
        root = self._documents_root(create=False)
        target = self._inside_root(Path(remote_path), root)
        try:
            if not target.exists():
                return TransportResult(True, "Documento já não existe no NAS.", str(target))
            if not target.is_file():
                raise TransportConfigurationError(
                    "O destino de exclusão NAS não é um arquivo regular."
                )
            target.unlink()
            return TransportResult(True, "Documento removido do NAS.", str(target))
        except TransportConfigurationError:
            raise
        except (PermissionError, OSError) as exc:
            raise TransportRetryableError(
                "Não foi possível remover o documento do NAS neste momento."
            ) from exc

    def exists(self, remote_path: str) -> bool:
        root = self._documents_root(create=False)
        return self._inside_root(Path(remote_path), root).is_file()

    def _endpoint_root(self, *, require_existing: bool) -> Path:
        if self.endpoint.startswith("\\\\") and os.name != "nt":
            raise TransportConfigurationError(
                "O compartilhamento UNC configurado requer Windows ou montagem pelo sistema operacional."
            )
        path = Path(self.endpoint).expanduser()
        if not path.is_absolute():
            raise TransportConfigurationError("O destino NAS deve ser um caminho absoluto.")
        try:
            return path.resolve(strict=require_existing)
        except FileNotFoundError as exc:
            raise TransportRetryableError("Destino NAS indisponível.") from exc
        except OSError as exc:
            raise TransportRetryableError("Destino NAS indisponível.") from exc

    def _documents_root(self, *, create: bool) -> Path:
        endpoint = self._endpoint_root(require_existing=True)
        if not endpoint.is_dir():
            raise TransportConfigurationError("O destino NAS não é um diretório.")
        root = (endpoint / "SmartFile" / self.organization_segment / "Documents").resolve()
        self._inside_root(root, endpoint)
        try:
            if create:
                root.mkdir(parents=True, exist_ok=True)
            elif not root.is_dir():
                raise TransportRetryableError("A raiz documental NAS está indisponível.")
        except (PermissionError, OSError) as exc:
            raise TransportRetryableError(
                "Não foi possível acessar a raiz documental no NAS."
            ) from exc
        return root

    @staticmethod
    def _inside_root(candidate: Path, root: Path) -> Path:
        resolved_root = Path(root).resolve()
        resolved = Path(candidate).expanduser().resolve()
        try:
            resolved.relative_to(resolved_root)
        except ValueError as exc:
            raise TransportConfigurationError(
                "Caminho recusado fora da raiz NAS da organização."
            ) from exc
        if resolved == resolved_root:
            raise TransportConfigurationError("O arquivo NAS não pode ser a própria raiz.")
        return resolved

    @staticmethod
    def _safe_remote_name(value: str) -> str:
        name = value.strip()
        if (
            not name or name in {".", ".."} or "/" in name or "\\" in name
            or Path(name).is_absolute() or "\x00" in name
        ):
            raise TransportConfigurationError("Nome remoto inválido.")
        return name

    @staticmethod
    def _local_file(path: Path) -> Path:
        try:
            resolved = Path(path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise TransportConfigurationError(
                "Arquivo local do documento não encontrado."
            ) from exc
        if not resolved.is_file():
            raise TransportConfigurationError("Arquivo local do documento inválido.")
        return resolved

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
