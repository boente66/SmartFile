from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.entities.organization_transport_entity import OrganizationTransportEntity
from app.repositories.organization_transport_repository import OrganizationTransportRepository
from app.services.audit_service import AuditService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)


class OrganizationTransportService:
    MODES = {"LOCAL", "NAS", "HTTPS", "LAN"}

    def __init__(self, database, context):
        self.context = context
        self.organizations = OrganizationService(database)
        self.repository = OrganizationTransportRepository(database=database)
        self.features = OrganizationFeatureService(database)
        self.audit = AuditService(database)

    def get(self, organization_id: int) -> OrganizationTransportEntity:
        self._require(organization_id)
        return self.repository.get(organization_id)

    def configure(
        self, organization_id: int, mode: str, endpoint: str | None,
        *, enabled: bool, verify_tls: bool = True,
    ) -> OrganizationTransportEntity:
        self._require(organization_id)
        previous = self.repository.get(organization_id)
        mode = mode.strip().upper()
        if mode not in self.MODES:
            raise ValueError("Modo de transporte inválido.")
        normalized = self._validate_endpoint(mode, endpoint)
        now = datetime.now(timezone.utc).isoformat()
        saved = self.repository.save(OrganizationTransportEntity(
            organization_id=organization_id, mode=mode, endpoint=normalized,
            enabled=bool(enabled and mode != "LOCAL"), verify_tls=bool(verify_tls),
            credential_ref=previous.credential_ref,
            updated_by_user_id=self.context.current_user.id, updated_at=now,
        ))
        self.audit.record(
            "TRANSPORT_CONFIGURED", user_id=self.context.current_user.id,
            organization_id=organization_id, target_type="transport",
            target_id=organization_id,
            description=f"Transporte {mode} {'ativado' if saved.enabled else 'configurado'}",
        )
        if previous.enabled != saved.enabled:
            self.audit.record(
                "TRANSPORT_ENABLED" if saved.enabled else "TRANSPORT_DISABLED",
                user_id=self.context.current_user.id,
                organization_id=organization_id,
                target_type="transport",
                target_id=organization_id,
                description=f"Transporte corporativo {'ativado' if saved.enabled else 'desativado'}",
            )
        logger.info(
            "corporate.transport.configured organization_id=%s mode=%s enabled=%s success=true",
            organization_id, mode, saved.enabled,
        )
        return saved

    def _require(self, organization_id: int) -> None:
        if organization_id != getattr(self.context.active_organization, "id", None):
            raise PermissionError("Ative a organização antes de configurar o transporte.")
        self.context.require_permission("transport.configure")
        organization = self.organizations.repository.find_by_id(organization_id)
        self.features.require(organization, "server_transport")

    @staticmethod
    def _validate_endpoint(mode: str, endpoint: str | None) -> str | None:
        value = (endpoint or "").strip()
        if mode == "LOCAL":
            return None
        if not value:
            raise ValueError("Informe o destino do transporte.")
        if mode == "NAS":
            if not (Path(value).expanduser().is_absolute() or value.startswith("\\\\")):
                raise ValueError("Informe um caminho NAS absoluto ou compartilhamento UNC.")
            return value
        if mode == "HTTPS":
            parsed = urlparse(value)
            if parsed.scheme.lower() != "https" or not parsed.hostname:
                raise ValueError("O servidor deve utilizar uma URL HTTPS válida.")
            if parsed.username or parsed.password:
                raise ValueError("Não informe credenciais diretamente na URL.")
            return value.rstrip("/")
        if not re.fullmatch(r"[A-Za-z0-9._:-]+(?:/[A-Za-z0-9._ -]+)*", value):
            raise ValueError("Informe um host ou compartilhamento LAN válido.")
        if ".." in value.split("/"):
            raise ValueError("O caminho LAN não pode conter navegação relativa.")
        return value
