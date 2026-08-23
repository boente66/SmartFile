from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class CloudFolderBrowseWorker(QThread):
    succeeded = pyqtSignal(object, object)
    failed = pyqtSignal(object, str)

    def __init__(self, provider, parent_id: str | None):
        super().__init__()
        self.provider = provider
        self.parent_id = parent_id

    def run(self) -> None:
        try:
            folders = self.provider.list_folders(self.parent_id)
            if not self.isInterruptionRequested():
                self.succeeded.emit(self.parent_id, folders)
        except Exception as exc:
            logger.warning(
                "cloud.folder.browse.failed parent_present=%s error=%s",
                bool(self.parent_id), type(exc).__name__,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(
                    self.parent_id,
                    str(exc) or "Não foi possível consultar as pastas do OneDrive.",
                )


class CloudFolderMappingWorker(QThread):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(
        self, service, organization_id: int, folder_id: int,
        remote_id: str, provider,
    ):
        super().__init__()
        self.service = service
        self.organization_id = organization_id
        self.folder_id = folder_id
        self.remote_id = remote_id
        self.provider = provider

    def run(self) -> None:
        try:
            result = self.service.map_existing_onedrive_folder(
                self.organization_id,
                self.folder_id,
                self.remote_id,
                provider=self.provider,
            )
            if not self.isInterruptionRequested():
                self.succeeded.emit(result)
        except Exception as exc:
            logger.warning(
                "cloud.folder.mapping.failed organization_id=%s folder_id=%s error=%s",
                self.organization_id, self.folder_id, type(exc).__name__,
            )
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc) or "Não foi possível mapear a pasta OneDrive.")
