from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.entities.organization_transport_entity import OrganizationTransportEntity
from app.entities.transport_target_entity import TransportTargetEntity
from app.models.transport_credential import TransportCredential
from app.repositories.organization_transport_repository import OrganizationTransportRepository
from app.repositories.transport_target_repository import TransportTargetRepository
from app.services.audit_service import AuditService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_service import OrganizationService
from app.services.corporate_transport_service import CorporateTransportService
from app.services.credential_vault_service import CredentialVaultService

logger = logging.getLogger(__name__)


class OrganizationTransportService:
    MODES = {"LOCAL", "NAS", "HTTPS", "LAN"}

    def __init__(self, database, context, *, credential_provider=None):
        self.database = database
        self.context = context
        self.organizations = OrganizationService(database)
        self.repository = OrganizationTransportRepository(database=database)
        self.targets = TransportTargetRepository(database=database)
        self.features = OrganizationFeatureService(database)
        self.audit = AuditService(database)
        self.corporate = CorporateTransportService(database)
        self.credentials = CredentialVaultService(
            database, context, credential_provider
        )

    def get(self, organization_id: int) -> OrganizationTransportEntity:
        self._require(organization_id)
        return self.repository.get(organization_id)

    def configure(
        self, organization_id: int, mode: str, endpoint: str | None,
        *, enabled: bool, verify_tls: bool = True,
        credential_username: str | None = None,
        credential_password: str | None = None,
        remove_credential: bool = False,
    ) -> OrganizationTransportEntity:
        self._require(organization_id)
        previous = self.repository.get(organization_id)
        mode = mode.strip().upper()
        if mode not in self.MODES:
            raise ValueError("Modo de transporte inválido.")
        normalized = self._validate_endpoint(mode, endpoint)
        if remove_credential and (credential_username or credential_password):
            raise ValueError(
                "Escolha substituir ou remover a credencial, não ambas as ações."
            )
        if bool(credential_username) != bool(credential_password):
            raise ValueError("Informe usuário e senha para substituir a credencial.")
        if mode == "LOCAL" and (credential_username or credential_password):
            raise ValueError("Credenciais só podem ser associadas a um destino remoto.")

        new_reference = None
        if credential_username and credential_password:
            new_reference = self.credentials.store(
                organization_id,
                TransportCredential(credential_username, credential_password),
            )
        if mode == "LOCAL" or remove_credential:
            desired_reference = None
        elif new_reference:
            desired_reference = new_reference
        else:
            desired_reference = previous.credential_ref
        now = datetime.now(timezone.utc).isoformat()
        current = (
            self.targets.find_by_id(previous.current_target_id, organization_id)
            if previous.current_target_id else None
        )
        try:
            with self.database.transaction():
                target = current
                target_changed = not self._same_physical_target(
                    current, mode, normalized, bool(verify_tls), desired_reference,
                )
                if mode == "LOCAL":
                    if current is not None and current.status == "ACTIVE":
                        self._retire_target(current, organization_id)
                    target = None
                elif target_changed:
                    if current is not None and current.status == "ACTIVE":
                        self._retire_target(current, organization_id)
                    target = self._create_target(
                        organization_id, mode, normalized or "",
                        desired_reference, bool(verify_tls), now,
                    )
                saved = self.repository.save(OrganizationTransportEntity(
                    organization_id=organization_id, mode=mode, endpoint=normalized,
                    enabled=bool(enabled and mode != "LOCAL"),
                    verify_tls=bool(verify_tls),
                    credential_ref=desired_reference,
                    current_target_id=(target.id if target else None),
                    updated_by_user_id=self.context.current_user.id, updated_at=now,
                ))
                self.audit.record(
                    "TRANSPORT_CONFIGURED", user_id=self.context.current_user.id,
                    organization_id=organization_id, target_type="transport",
                    target_id=organization_id,
                    description=(
                        f"Transporte {mode} "
                        f"{'ativado' if saved.enabled else 'configurado'}"
                    ),
                )
                if previous.enabled != saved.enabled:
                    self.audit.record(
                        "TRANSPORT_ENABLED" if saved.enabled else "TRANSPORT_DISABLED",
                        user_id=self.context.current_user.id,
                        organization_id=organization_id, target_type="transport",
                        target_id=organization_id,
                        description=(
                            "Transporte corporativo "
                            f"{'ativado' if saved.enabled else 'desativado'}"
                        ),
                    )
                if new_reference:
                    self.audit.record(
                        (
                            "TRANSPORT_CREDENTIAL_ROTATED"
                            if previous.credential_ref
                            else "TRANSPORT_CREDENTIAL_CONFIGURED"
                        ),
                        user_id=self.context.current_user.id,
                        organization_id=organization_id,
                        target_type="transport", target_id=organization_id,
                        description="Credencial do transporte atualizada.",
                    )
                elif (
                    (remove_credential or mode == "LOCAL")
                    and previous.credential_ref
                ):
                    self.audit.record(
                        "TRANSPORT_CREDENTIAL_REMOVED",
                        user_id=self.context.current_user.id,
                        organization_id=organization_id,
                        target_type="transport", target_id=organization_id,
                        description=(
                            "Credencial removida da configuração atual; "
                            "referências históricas foram preservadas."
                        ),
                    )
        except Exception:
            if new_reference:
                try:
                    self.credentials.discard_compensation(
                        organization_id, new_reference
                    )
                except Exception:
                    logger.exception(
                        "corporate.transport.credential_compensation_failed "
                        "organization_id=%s", organization_id,
                    )
            raise

        if (
            previous.credential_ref
            and previous.credential_ref != desired_reference
            and previous.credential_ref.startswith(
                f"smartfile:transport:{organization_id}:"
            )
        ):
            try:
                self.credentials.delete_if_unused(
                    organization_id, previous.credential_ref
                )
            except Exception:
                logger.warning(
                    "corporate.transport.old_credential_preserved "
                    "organization_id=%s", organization_id,
                    exc_info=True,
                )
        logger.info(
            "corporate.transport.configured organization_id=%s mode=%s enabled=%s success=true",
            organization_id, mode, saved.enabled,
        )
        return saved

    def test_connection(
        self, organization_id: int, mode: str, endpoint: str | None,
    ):
        self._require(organization_id)
        selected_mode = mode.strip().upper()
        if selected_mode not in self.MODES:
            raise ValueError("Modo de transporte inválido.")
        normalized = self._validate_endpoint(selected_mode, endpoint)
        return self.corporate.test_connection(
            organization_id, mode=selected_mode, endpoint=normalized,
            actor_user_id=self.context.current_user.id,
        )

    def summary(self, organization_id: int) -> dict:
        self._require(organization_id)
        return self.corporate.summary(organization_id)

    def retry_failed(self, organization_id: int) -> int:
        self._require(organization_id)
        count = self.corporate.retry_failed(organization_id)
        if count:
            self.audit.record(
                "TRANSPORT_RETRY_REQUESTED",
                user_id=self.context.current_user.id,
                organization_id=organization_id,
                target_type="transport",
                target_id=organization_id,
                description=f"Nova tentativa solicitada para {count} job(s).",
            )
        return count

    def list_reconciliation(self, organization_id: int):
        self._require(organization_id)
        return self.corporate.queue.repository.list_reconciliation_required(
            organization_id
        )

    def cancel_reconciliation(self, organization_id: int, job_id: int) -> bool:
        self._require(organization_id)
        return self.corporate.cancel_reconciliation(
            organization_id, job_id,
            actor_user_id=self.context.current_user.id,
        )

    def recreate_upload(self, organization_id: int, job_id: int):
        self._require(organization_id)
        return self.corporate.recreate_upload_for_current_target(
            organization_id, job_id,
            actor_user_id=self.context.current_user.id,
        )

    def _create_target(
        self, organization_id: int, mode: str, endpoint: str,
        credential_ref: str | None, verify_tls: bool, created_at: str,
    ):
        target = self.targets.create(TransportTargetEntity(
            organization_id=organization_id, mode=mode, endpoint=endpoint,
            credential_ref=credential_ref, verify_tls=verify_tls,
            fingerprint=self._fingerprint(
                organization_id, mode, endpoint, verify_tls, credential_ref
            ),
            created_by_user_id=self.context.current_user.id,
            created_at=created_at,
        ))
        self.audit.record(
            "TRANSPORT_TARGET_CREATED", user_id=self.context.current_user.id,
            organization_id=organization_id, target_type="transport_target",
            target_id=target.id,
            description=f"Novo destino físico {mode} criado.",
        )
        self.audit.record(
            "TRANSPORT_TARGET_ACTIVATED", user_id=self.context.current_user.id,
            organization_id=organization_id, target_type="transport_target",
            target_id=target.id,
            description="Destino físico definido como atual.",
        )
        return target

    def _retire_target(self, target, organization_id: int) -> None:
        if self.targets.retire(target.id, organization_id):
            self.audit.record(
                "TRANSPORT_TARGET_RETIRED",
                user_id=self.context.current_user.id,
                organization_id=organization_id,
                target_type="transport_target", target_id=target.id,
                description="Destino físico anterior preservado como histórico.",
            )

    @staticmethod
    def _same_physical_target(
        target, mode: str, endpoint: str | None,
        verify_tls: bool, credential_ref: str | None,
    ) -> bool:
        return bool(
            target is not None and target.status == "ACTIVE"
            and target.mode == mode and target.endpoint == (endpoint or "")
            and target.verify_tls == verify_tls
            and target.credential_ref == credential_ref
        )

    @staticmethod
    def _fingerprint(
        organization_id: int, mode: str, endpoint: str,
        verify_tls: bool, credential_ref: str | None,
    ) -> str:
        material = "\0".join((
            str(organization_id), mode, endpoint,
            "1" if verify_tls else "0", credential_ref or "",
        ))
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

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
