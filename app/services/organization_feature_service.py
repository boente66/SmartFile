from __future__ import annotations

from datetime import datetime, timezone

from app.entities.organization_feature_setting_entity import OrganizationFeatureSettingEntity
from app.models.organization_features import OrganizationFeatureCatalog, OrganizationFeatureSet
from app.repositories.organization_feature_setting_repository import (
    OrganizationFeatureSettingRepository,
)
from app.services.audit_service import AuditService


class OrganizationFeatureService(OrganizationFeatureCatalog):
    """Resolve capacidade do perfil e ativação administrativa por organização."""

    def __init__(self, database=None, context=None):
        self.database = database
        self.context = context
        self.repository = (
            OrganizationFeatureSettingRepository(database=database) if database else None
        )
        self.audit = AuditService(database) if database else None

    def for_organization(self, organization) -> OrganizationFeatureSet:
        available = self.capabilities_for_organization(organization)
        if self.repository is None or getattr(organization, "id", None) is None:
            return available
        settings = self.repository.find_by_organization(int(organization.id))
        enabled_codes = (
            frozenset(item.feature_code for item in settings if item.enabled)
            if settings
            else self.default_enabled_codes(available.profile_code)
        )
        return OrganizationFeatureSet(
            profile_code=available.profile_code,
            profile_name=available.profile_name,
            features=tuple(
                feature for feature in available.features if feature.code in enabled_codes
            ),
        )

    def initialize_defaults(
        self, organization, *, user_id: int | None = None,
    ) -> OrganizationFeatureSet:
        if self.repository is None or organization.id is None:
            return self.for_organization(organization)
        available = self.capabilities_for_organization(organization)
        existing = {
            item.feature_code
            for item in self.repository.find_by_organization(int(organization.id))
        }
        defaults = self.default_enabled_codes(available.profile_code)
        now = self._now()
        self.repository.save_all([
            OrganizationFeatureSettingEntity(
                organization_id=int(organization.id),
                feature_code=feature.code,
                enabled=feature.code in defaults,
                updated_by_user_id=user_id,
                updated_at=now,
            )
            for feature in available.features
            if feature.code not in existing
        ])
        return self.for_organization(organization)

    def update_enabled_features(
        self, organization, enabled_codes: set[str] | frozenset[str],
        *, authorization_checked: bool = False,
    ) -> OrganizationFeatureSet:
        if self.repository is None or self.context is None:
            raise RuntimeError("Contexto administrativo indisponível.")
        if not authorization_checked:
            if organization.id != getattr(self.context.active_organization, "id", None):
                raise PermissionError("Ative a organização antes de alterar seus recursos.")
            self.context.require_permission("organization.update")
        available = self.capabilities_for_organization(organization)
        invalid = set(enabled_codes) - set(available.codes)
        if invalid:
            raise ValueError("Um ou mais recursos não pertencem ao perfil selecionado.")
        if "server_transport" in enabled_codes and not authorization_checked:
            self.context.require_permission("transport.configure")
        previous = self.for_organization(organization).codes
        now = self._now()
        user_id = getattr(self.context.current_user, "id", None)
        with self.database.transaction():
            self.repository.save_all([
                OrganizationFeatureSettingEntity(
                    organization_id=int(organization.id),
                    feature_code=feature.code,
                    enabled=feature.code in enabled_codes,
                    updated_by_user_id=user_id,
                    updated_at=now,
                )
                for feature in available.features
            ])
            for code in sorted(previous ^ frozenset(enabled_codes)):
                self.audit.record(
                    "ORGANIZATION_FEATURE_ENABLED" if code in enabled_codes
                    else "ORGANIZATION_FEATURE_DISABLED",
                    user_id=user_id,
                    organization_id=int(organization.id),
                    target_type="organization_feature",
                    target_id=int(organization.id),
                    description=f"Recurso {code} {'ativado' if code in enabled_codes else 'desativado'}",
                )
        return self.for_organization(organization)

    def require_available(self, organization, feature_code: str) -> None:
        if feature_code not in self.FEATURES:
            raise ValueError("Recurso organizacional desconhecido.")
        if not self.capabilities_for_organization(organization).has(feature_code):
            raise PermissionError("Este recurso está disponível somente no perfil compatível.")

    def require(self, organization, feature_code: str) -> None:
        self.require_available(organization, feature_code)
        if not self.for_organization(organization).has(feature_code):
            raise PermissionError("Este recurso não está habilitado para a organização.")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
