from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from app.cloud.cloud_models import CloudStorageQuota, CloudStorageQuotaStatus
from app.cloud.cloud_provider import (
    CloudAuthenticationError, CloudOfflineError, CloudPermissionDeniedError,
)
from app.errors.cloud_exceptions import CloudTokenExpiredError

logger = logging.getLogger(__name__)


class CloudStorageQuotaWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(object)

    def __init__(self, service, organization_id: int, provider: str):
        super().__init__()
        self.service = service
        self.organization_id = organization_id
        self.provider = provider

    def run(self) -> None:
        try:
            quota = self.service.fetch(self.organization_id)
            if quota is not None:
                self.succeeded.emit(quota)
        except (CloudAuthenticationError, CloudTokenExpiredError) as exc:
            self.failed.emit(self._failure(
                CloudStorageQuotaStatus.AUTHENTICATION_REQUIRED, str(exc)
            ))
        except CloudOfflineError as exc:
            self.failed.emit(self._failure(
                CloudStorageQuotaStatus.TEMPORARILY_UNAVAILABLE, str(exc)
            ))
        except CloudPermissionDeniedError as exc:
            self.failed.emit(self._failure(
                CloudStorageQuotaStatus.PERMISSION_DENIED, str(exc)
            ))
        except Exception as exc:
            logger.warning(
                "cloud.quota.failed organization_id=%s provider=%s error=%s",
                self.organization_id, self.provider, type(exc).__name__,
            )
            self.failed.emit(self._failure(
                CloudStorageQuotaStatus.TEMPORARILY_UNAVAILABLE,
                str(exc) or "Não foi possível consultar a capacidade da nuvem.",
            ))

    def _failure(self, status, message: str) -> CloudStorageQuota:
        snapshot = self.service.last_known(self.organization_id)
        return CloudStorageQuota(
            provider=self.provider,
            total_bytes=snapshot.total_bytes if snapshot else None,
            used_bytes=snapshot.used_bytes if snapshot else None,
            available_bytes=snapshot.available_bytes if snapshot else None,
            fetched_at=snapshot.fetched_at if snapshot else None,
            status=status,
            provider_state=snapshot.provider_state if snapshot else None,
            message=message,
        )
