from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.cloud.cloud_models import CloudAuthResult, CloudUploadRequest, RemoteMetadata
from app.errors.storage_exceptions import CloudStorageLimitError

logger = logging.getLogger(__name__)

NETWORK_TIMEOUT_SECONDS = 30


class CloudError(RuntimeError):
    pass


class CloudAuthenticationError(CloudError):
    pass


class CloudOfflineError(CloudError):
    pass


class CloudConflictError(CloudError):
    pass


class CloudPermissionDeniedError(CloudError):
    pass


class CloudResourceNotFoundError(CloudError):
    pass


class CloudRateLimitError(CloudError):
    def __init__(self, message: str, retry_after: str | None = None):
        self.retry_after = retry_after
        super().__init__(message)


class CloudFileTooLargeError(CloudError):
    pass


Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, dict[str, str], bytes]]


def urllib_transport(method: str, url: str, headers: dict[str, str], data: bytes | None):
    request = Request(url, data=data, headers=headers, method=method)
    target = _safe_request_target(url)
    started_at = time.monotonic()
    logger.debug("cloud.http.start method=%s target=%s", method, target)
    try:
        with urlopen(request, timeout=NETWORK_TIMEOUT_SECONDS) as response:
            result = response.status, dict(response.headers.items()), response.read()
            logger.debug(
                "cloud.http.done method=%s target=%s status=%s elapsed=%.3fs",
                method, target, response.status, time.monotonic() - started_at,
            )
            return result
    except HTTPError as exc:
        body = exc.read()
        headers = dict(exc.headers.items()) if exc.headers else {}
        if exc.code == 308:
            return exc.code, headers, body
        logger.warning(
            "cloud.http.error method=%s target=%s status=%s elapsed=%.3fs",
            method, target, exc.code, time.monotonic() - started_at,
        )
        raise _http_status_error(exc.code, headers, body) from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "cloud.http.timeout_or_offline method=%s target=%s elapsed=%.3fs error=%s",
            method, target, time.monotonic() - started_at, type(exc).__name__,
        )
        raise CloudOfflineError(
            f"O provedor de nuvem não respondeu em até {NETWORK_TIMEOUT_SECONDS} segundos."
        ) from exc


def _http_status_error(
    status: int, headers: dict[str, str], body: bytes,
) -> Exception:
    if status == 401:
        return CloudAuthenticationError(
            "A autorização da nuvem expirou ou foi removida. Conecte novamente sua conta."
        )
    if status == 409:
        return CloudConflictError("O provedor informou um conflito remoto.")
    quota_markers = (
        b"quota", b"storagelimit", b"storagequota", b"insufficientstorage",
    )
    lowered_body = body.lower()
    if status == 413:
        return CloudFileTooLargeError(
            "O arquivo excede o tamanho aceito pelo provedor de nuvem."
        )
    if status == 507 or (
        status == 403 and any(marker in lowered_body for marker in quota_markers)
    ):
        return CloudStorageLimitError(
            "O armazenamento da nuvem está cheio. O documento local foi preservado."
        )
    if status == 403:
        return CloudPermissionDeniedError(
            "A conta não possui permissão para executar esta operação na nuvem."
        )
    if status == 404:
        return CloudResourceNotFoundError(
            "O arquivo ou a pasta não foi encontrado no provedor de nuvem."
        )
    if status == 429:
        return CloudRateLimitError(
            "O provedor limitou temporariamente as solicitações. A operação será repetida.",
            headers.get("Retry-After") or headers.get("retry-after"),
        )
    if 500 <= status <= 599:
        return CloudOfflineError(
            f"O provedor de nuvem está temporariamente indisponível (HTTP {status})."
        )
    return CloudError(f"Falha no provedor de nuvem (HTTP {status}).")


def _safe_request_target(url: str) -> str:
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


class CloudProvider(ABC):
    """Contrato único obrigatório para todos os provedores."""

    def __init__(self, access_token: str = "", transport: Transport | None = None):
        self.access_token = access_token
        self._transport = transport or urllib_transport

    @abstractmethod
    def authenticate(self, credentials: dict[str, str]) -> CloudAuthResult: ...

    @abstractmethod
    def refresh_token(self, refresh_token: str, credentials: dict[str, str]) -> CloudAuthResult: ...

    @abstractmethod
    def upload(self, request: CloudUploadRequest) -> RemoteMetadata: ...

    @abstractmethod
    def download(self, remote_id: str, destination: Path) -> Path: ...

    @abstractmethod
    def delete(self, remote_id: str) -> None: ...

    @abstractmethod
    def rename(self, remote_id: str, new_name: str) -> RemoteMetadata: ...

    @abstractmethod
    def move(self, remote_id: str, parent_id: str) -> RemoteMetadata: ...

    @abstractmethod
    def list_changes(self, cursor: str | None = None) -> tuple[list[RemoteMetadata], str | None]: ...

    @abstractmethod
    def get_metadata(self, remote_id: str) -> RemoteMetadata: ...

    @abstractmethod
    def ensure_folder(self, name: str, parent_id: str | None = None) -> RemoteMetadata:
        """Localiza ou cria uma pasta de forma idempotente."""
        ...

    @abstractmethod
    def disconnect(self) -> None: ...

    def _authorized(self, content_type: str = "application/json") -> dict[str, str]:
        if not self.access_token:
            raise CloudAuthenticationError("Conta de nuvem não autenticada.")
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": content_type}

    def _json_request(
        self, method: str, url: str, payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]:
        request_headers = headers or self._authorized()
        data = json.dumps(payload).encode() if payload is not None else None
        status, response_headers, body = self._transport(
            method, url, request_headers, data
        )
        if status >= 400 and status != 308:
            raise _http_status_error(status, response_headers, body)
        try:
            result = json.loads(body.decode()) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CloudError(
                "O provedor de nuvem retornou uma resposta inválida."
            ) from exc
        if isinstance(result, dict) and result.get("error"):
            error = result["error"]
            code = (
                str(error.get("code", "UNKNOWN"))
                if isinstance(error, dict) else "UNKNOWN"
            )
            message = (
                str(error.get("message", ""))
                .replace("\r", " ")
                .replace("\n", " ")[:300]
                if isinstance(error, dict) else ""
            )
            detail = f": {message}" if message else ""
            raise CloudError(f"O provedor de nuvem retornou o erro {code}{detail}")
        return result, response_headers
