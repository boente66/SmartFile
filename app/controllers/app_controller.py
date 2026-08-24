import logging
import os
import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QApplication, QMessageBox

from app.controllers.corporate_transport_controller import CorporateTransportController
from app.controllers.convert_controller import ConvertController
from app.controllers.document_controller import DocumentController
from app.controllers.capture_pdf_controller import CapturePdfController
from app.controllers.document_request_controller import DocumentRequestController
from app.controllers.document_delivery_controller import DocumentDeliveryController
from app.controllers.organization_settings_controller import OrganizationSettingsController
from app.controllers.pdf_viewer_controller import PDFViewerController
from app.controllers.pdf_signature_controller import PDFSignatureController
from app.controllers.handwritten_signature_controller import HandwrittenSignatureController
from app.services.document_service import DocumentService
from app.services.version_notification_service import VersionNotificationService
from app.services.application_update_service import ApplicationUpdateService
from app.workers.application_update_worker import ApplicationUpdateWorker
from app.coordinators.corporate_transport_coordinator import CorporateTransportCoordinator
from app.version import __version__

logger = logging.getLogger(__name__)


class AppController:
    """
    Controller principal da aplicação.
    """

    def __init__(self, main_view, session_context=None, database=None):
        self.main_view = main_view
        self.session_context = session_context
        self.database = database
        self.workspace = main_view.workspace

        # Controllers ainda NÃO ativos
        self.convert_controller = None
        self.pdf_controller = None
        self.pdf_viewer_controller = None
        self.pdf_signature_controller = None
        self.handwritten_signature_controller = None
        self.scan_controller = None
        self.capture_pdf_controller = None
        self.document_controller = None
        self.document_request_controller = None
        self.document_delivery_controller = None
        self.transport_controller = None
        self.transport_coordinator = None
        self.organization_settings_controller = None
        self.version_notifications = None
        self._update_worker = None
        self._application = None
        self._stopped = False

    def start(self):
        """
        Inicializa funcionalidades do sistema.
        Chamado após UI estar pronta.
        """
        # Criar controllers
        self.convert_controller = ConvertController(self.workspace, self.main_view)
        self.pdf_viewer_controller = PDFViewerController(self.workspace)
        self.pdf_signature_controller = PDFSignatureController(
            self.main_view, self.pdf_viewer_controller
        )
        self.handwritten_signature_controller = HandwrittenSignatureController(
            self.main_view, self.pdf_viewer_controller
        )
        document_service = (
            DocumentService(database=self.database)
            if self.database else DocumentService()
        )
        self.capture_pdf_controller = CapturePdfController(
            self.workspace,
            document_service,
            session_context=self.session_context,
        )
        # Compatibilidade de API durante a transição: as rotas históricas
        # Scanner e PDF Tools apontam para a experiência integrada.
        self.pdf_controller = self.capture_pdf_controller
        self.scan_controller = self.capture_pdf_controller
        self.transport_coordinator = CorporateTransportCoordinator(
            document_service.database,
            self.session_context,
            service=document_service.corporate_transport_service,
            parent=self.main_view,
        )
        self.document_controller = DocumentController(
            self.workspace,
            self.main_view,
            convert_controller=self.convert_controller,
            pdf_controller=self.pdf_controller,
            pdf_viewer_controller=self.pdf_viewer_controller,
            session_context=self.session_context,
            document_service=document_service,
            transport_job_notifier=self.transport_coordinator.trigger,
        )
        self.document_request_controller = DocumentRequestController(
            document_service.database,
            self.session_context,
            parent=self.document_controller.view,
            organization_id_provider=lambda: document_service.active_organization_id,
        )
        self.document_delivery_controller = DocumentDeliveryController(
            self.workspace, document_service, self.session_context,
            parent=self.document_controller.view,
            pdf_viewer_controller=self.pdf_viewer_controller,
            main_view=self.main_view,
        )
        self.transport_controller = CorporateTransportController(
            document_service.database,
            self.session_context,
            parent=self.document_controller.view,
            organization_id_provider=lambda: document_service.active_organization_id,
        )
        self.organization_settings_controller = OrganizationSettingsController(
            document_service,
            self.session_context,
            parent=self.document_controller.view,
            refresh_callback=self.document_controller.refresh_organization_state,
            transport_controller=self.transport_controller,
        )
        self._connect_enterprise_layer()
        self.capture_pdf_controller.imported_callback = (
            self.document_controller.on_refresh_documents
        )
        self.pdf_signature_controller.set_document_service(
            self.document_controller.service
        )
        self.handwritten_signature_controller.set_document_service(
            self.document_controller.service
        )

        # Conectar navegação
        self.main_view.sidebar.tool_selected.connect(self.on_tool_selected)

        # Tela inicial
        self.document_controller.activate()
        self.transport_coordinator.start()
        self.document_delivery_controller.start()
        self.main_view.sidebar.set_active_tool("documents")
        self._application = QApplication.instance()
        if self._application is not None:
            self._application.aboutToQuit.connect(self.shutdown)
        if self.database:
            notifications = VersionNotificationService(self.database)
            self.version_notifications = notifications
            self.main_view.version_notification_acknowledged.connect(
                notifications.acknowledge
            )
            if notifications.should_notify():
                self.main_view.show_version_notification(
                    __version__, notifications.message(),
                )
        if getattr(sys, "frozen", False) or os.getenv("SMARTFILE_CHECK_UPDATES") == "1":
            self._start_update_check()

    def _start_update_check(self) -> None:
        service = ApplicationUpdateService(__version__)
        worker = ApplicationUpdateWorker(service)
        self._update_worker = worker
        self.main_view.update_download_requested.connect(self._open_update_download)
        worker.update_available.connect(self.main_view.show_application_update)
        worker.finished.connect(lambda w=worker: self._cleanup_update_worker(w))
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _cleanup_update_worker(self, worker) -> None:
        if self._update_worker is worker:
            self._update_worker = None

    @staticmethod
    def _open_update_download(url: str) -> None:
        if not url.startswith("https://github.com/boente66/SmartFile/"):
            logger.warning("application.update.rejected_untrusted_url")
            return
        QDesktopServices.openUrl(QUrl(url))

    def on_tool_selected(self, tool_name: str):
        if tool_name != "documents":
            self.main_view.sidebar.show()
        if tool_name == "converter":
            self.convert_controller.activate()
        elif tool_name in {"capture_pdf", "pdf", "scanner"}:
            self.capture_pdf_controller.activate()
        elif tool_name == "documents":
            self.document_controller.activate()
        elif tool_name == "deliveries":
            self.document_delivery_controller.activate()

    def _connect_enterprise_layer(self) -> None:
        view = self.document_controller.view
        settings = self.organization_settings_controller
        transport = self.transport_controller
        coordinator = self.transport_coordinator

        view.organization_changed.connect(settings.activate_organization)
        view.create_organization_requested.connect(settings.create_organization)
        view.edit_organization_requested.connect(settings.open_general_settings)
        view.delete_organization_requested.connect(settings.delete_organization)
        view.configure_transport_requested.connect(
            settings.open_infrastructure_settings
        )
        view.audit_history_requested.connect(settings.open_security_history)
        view.document_requests_requested.connect(
            self.document_delivery_controller.activate
        )

        settings.organization_changed.connect(coordinator.organization_changed)
        settings.organization_changed.connect(
            self.document_delivery_controller.organization_changed
        )
        settings.status_changed.connect(view.set_status)
        settings.failed.connect(
            lambda message: QMessageBox.warning(
                view, "Configurações da organização", message
            )
        )
        transport.configuration_saved.connect(coordinator.trigger)
        transport.retry_enqueued.connect(coordinator.trigger)
        transport.status_changed.connect(view.set_status)
        transport.failed.connect(
            lambda message: QMessageBox.warning(
                view, "Transporte empresarial", message
            )
        )
        coordinator.progress.connect(self._on_transport_progress)
        coordinator.succeeded.connect(self._on_transport_succeeded)
        coordinator.failed.connect(self._on_transport_failed)

    def _on_transport_progress(self, value: int, message: str) -> None:
        self.main_view.status.showMessage(f"{message} {value}%")

    def _on_transport_succeeded(self, summary: dict) -> None:
        if not summary.get("jobs"):
            return
        self.main_view.status.showMessage(
            "Transporte NAS: "
            f"{summary.get('completed', 0)} concluído(s), "
            f"{summary.get('retry', 0)} aguardando nova tentativa, "
            f"{summary.get('failed', 0)} falha(s)."
        )

    def _on_transport_failed(self, message: str) -> None:
        logger.error("corporate.transport.application.failed message=%s", message)
        self.main_view.status.showMessage(
            f"Falha no transporte corporativo: {message}"
        )

    def shutdown(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self.transport_controller is not None:
            self.transport_controller.shutdown()
        if self.transport_coordinator is not None:
            self.transport_coordinator.shutdown()
        if self.document_delivery_controller is not None:
            self.document_delivery_controller.shutdown()
        if self.document_controller is not None:
            self.document_controller.shutdown()
        if self._update_worker is not None:
            self._update_worker.requestInterruption()
        if self._application is not None:
            try:
                self._application.aboutToQuit.disconnect(self.shutdown)
            except TypeError:
                pass
            self._application = None
