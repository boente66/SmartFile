from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from app.services.corporate_transport_service import CorporateTransportService
from app.workers.transport_worker import TransportWorker

logger = logging.getLogger(__name__)


class CorporateTransportCoordinator(QObject):
    """Mantém o processamento NAS vivo fora da tela de Documentos."""

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    _active_workers: dict[tuple[str, int], TransportWorker] = {}

    def __init__(
        self, database, session_context, *, service=None, parent=None,
        interval_ms: int = 60_000, worker_factory=TransportWorker,
    ):
        super().__init__(parent)
        self.database = database
        self.session_context = session_context
        self.service = service or CorporateTransportService(database)
        self.worker_factory = worker_factory
        self._worker = None
        self._worker_organization_id: int | None = None
        self._pending_organization_id: int | None = None
        self._stopping = False
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.trigger)

    def start(self) -> None:
        self._stopping = False
        if not self.timer.isActive():
            self.timer.start()
        QTimer.singleShot(0, self.trigger)

    def trigger(self, organization_id: int | None = None) -> bool:
        if self._stopping or not self._session_ready():
            return False
        active_id = int(self.session_context.active_organization.id)
        target_id = int(organization_id or active_id)
        if target_id != active_id:
            logger.info(
                "corporate.transport.coordinator.skip_inactive organization_id=%s active=%s",
                target_id, active_id,
            )
            return False
        if self._worker is not None and self._worker.isRunning():
            self._pending_organization_id = target_id
            return False
        key = self._worker_key(target_id)
        active = self._active_workers.get(key)
        if active is not None and active.isRunning():
            logger.info(
                "corporate.transport.coordinator.duplicate_prevented organization_id=%s",
                target_id,
            )
            return False
        if active is not None:
            self._active_workers.pop(key, None)
        try:
            if not self.service.automatic_processing_enabled(target_id):
                logger.debug(
                    "corporate.transport.coordinator.paused organization_id=%s",
                    target_id,
                )
                return False
            if self.service.queue.next_pending(target_id) is None:
                return False
        except Exception as exc:
            self._emit_failure(exc, target_id)
            return False

        worker = self.worker_factory(
            lambda progress, cancelled: self.service.process_pending(
                target_id, progress, cancelled,
            )
        )
        self._worker = worker
        self._worker_organization_id = target_id
        self._active_workers[key] = worker
        worker.progress.connect(self.progress.emit)
        worker.succeeded.connect(
            lambda summary, organization_id=target_id:
            self._on_succeeded(organization_id, summary)
        )
        worker.failed.connect(
            lambda message, organization_id=target_id:
            self._on_failed(organization_id, message)
        )
        worker.finished.connect(
            lambda worker=worker, organization_id=target_id:
            self._cleanup_worker(worker, organization_id)
        )
        worker.finished.connect(worker.deleteLater)
        logger.info(
            "corporate.transport.coordinator.start organization_id=%s", target_id,
        )
        worker.start()
        return True

    def organization_changed(self, organization_id: int) -> None:
        target_id = int(organization_id)
        if (
            self._worker is not None
            and self._worker.isRunning()
            and self._worker_organization_id != target_id
        ):
            self._pending_organization_id = target_id
            self._worker.requestInterruption()
            logger.info(
                "corporate.transport.coordinator.cancel_for_switch from=%s to=%s",
                self._worker_organization_id, target_id,
            )
            return
        self.trigger(target_id)

    def shutdown(self, wait_ms: int = 5_000) -> None:
        self._stopping = True
        self.timer.stop()
        self._pending_organization_id = None
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            if not worker.wait(wait_ms):
                logger.warning(
                    "corporate.transport.coordinator.shutdown_timeout organization_id=%s",
                    self._worker_organization_id,
                )

    def is_running(self) -> bool:
        return bool(self._worker is not None and self._worker.isRunning())

    def _on_succeeded(self, organization_id: int, summary: dict) -> None:
        result = dict(summary)
        result["organization_id"] = organization_id
        logger.info(
            "corporate.transport.coordinator.succeeded organization_id=%s summary=%s",
            organization_id, summary,
        )
        self.succeeded.emit(result)

    def _on_failed(self, organization_id: int, message: str) -> None:
        logger.error(
            "corporate.transport.coordinator.failed organization_id=%s message=%s",
            organization_id, message,
        )
        self.failed.emit(message)

    def _cleanup_worker(self, worker, organization_id: int) -> None:
        key = self._worker_key(organization_id)
        if self._active_workers.get(key) is worker:
            self._active_workers.pop(key, None)
        if self._worker is worker:
            self._worker = None
            self._worker_organization_id = None
        pending = self._pending_organization_id
        self._pending_organization_id = None
        logger.info(
            "corporate.transport.coordinator.cleanup organization_id=%s", organization_id,
        )
        if not self._stopping and pending is not None:
            QTimer.singleShot(0, lambda: self.trigger(pending))

    def _emit_failure(self, exc: Exception, organization_id: int) -> None:
        message = str(exc).strip() or "Falha no transporte corporativo."
        logger.exception(
            "corporate.transport.coordinator.queue_failed organization_id=%s",
            organization_id,
        )
        self.failed.emit(message)

    def _worker_key(self, organization_id: int) -> tuple[str, int]:
        database_name = str(Path(self.database.db_name).expanduser().resolve())
        return database_name, organization_id

    def _session_ready(self) -> bool:
        return bool(
            self.session_context
            and self.session_context.is_authenticated()
            and self.session_context.active_organization is not None
        )
