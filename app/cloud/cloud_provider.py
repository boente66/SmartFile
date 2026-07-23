from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.cloud.cloud_models import CloudAuthResult, CloudUploadRequest, RemoteMetadata
from app.errors.storage_exceptions import CloudStorageLimitError


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
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        body = exc.read()
        headers = dict(exc.headers.items()) if exc.headers else {}
        if exc.code == 308:
            return exc.code, headers, body
        if exc.code == 401:
            raise CloudAuthenticationError(
                "A autorização da nuvem expirou ou foi removida. Conecte novamente sua conta."
            ) from exc
        if exc.code == 409:
            raise CloudConflictError("O provedor informou um conflito remoto.") from exc
        quota_markers = (b"quota", b"storageLimit", b"storageQuota", b"insufficientStorage")
        if exc.code == 413:
            raise CloudFileTooLargeError(
                "O arquivo excede o tamanho aceito pelo provedor de nuvem."
            ) from exc
        if exc.code == 507 or (exc.code == 403 and any(marker.lower() in body.lower() for marker in quota_markers)):
            raise CloudStorageLimitError(
                "O armazenamento da nuvem está cheio. O documento local foi preservado."
            ) from exc
        if exc.code == 403:
            raise CloudPermissionDeniedError(
                "A conta não possui permissão para executar esta operação na nuvem."
            ) from exc
        if exc.code == 404:
            raise CloudResourceNotFoundError(
                "O arquivo ou a pasta não foi encontrado no provedor de nuvem."
            ) from exc
        if exc.code == 429:
            raise CloudRateLimitError(
                "O provedor limitou temporariamente as solicitações. A operação será repetida.",
                headers.get("Retry-After") or headers.get("retry-after"),
            ) from exc
        if 500 <= exc.code <= 599:
            raise CloudOfflineError(
                "O provedor de nuvem está temporariamente indisponível."
            ) from exc
        raise CloudError(f"Falha no provedor de nuvem (HTTP {exc.code}).") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise CloudOfflineError("Não foi possível acessar o provedor de nuvem.") from exc


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
        _status, response_headers, body = self._transport(method, url, request_headers, data)
        return (json.loads(body.decode()) if body else {}), response_headers
