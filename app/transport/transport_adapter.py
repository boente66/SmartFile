from __future__ import annotations

from abc import ABC, abstractmethod

from app.transport.transport_models import TransportResult, TransportUploadRequest


class TransportAdapter(ABC):
    """Contrato mínimo dos conectores físicos de transporte corporativo."""

    @abstractmethod
    def test_connection(self) -> TransportResult:
        raise NotImplementedError

    @abstractmethod
    def upload(self, request: TransportUploadRequest) -> TransportResult:
        raise NotImplementedError

    @abstractmethod
    def delete(self, remote_path: str) -> TransportResult:
        raise NotImplementedError

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        raise NotImplementedError
