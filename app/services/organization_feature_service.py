from __future__ import annotations

from datetime import datetime, timezone

from app.entities.organization_feature_setting_entity import OrganizationFeatureSettingEntity
from app.models.organization_features import OrganizationFeature, OrganizationFeatureSet
from app.repositories.organization_feature_setting_repository import (
    OrganizationFeatureSettingRepository,
)
from app.services.audit_service import AuditService


class OrganizationFeatureService:
    """Resolve capacidade do perfil e ativação administrativa por organização."""

    FEATURES = {
        "contextual_actions": OrganizationFeature(
            "contextual_actions", "Ações contextuais", "Copiar, colar, renomear e mover para a lixeira."
        ),
        "smart_search": OrganizationFeature(
            "smart_search", "Busca inteligente", "Busca combinada por termos e metadados."
        ),
        "indexed_filters": OrganizationFeature(
            "indexed_filters", "Filtros indexados", "Filtros rápidos por tipo, origem, período e favorito."
        ),
        "cloud_sync": OrganizationFeature(
            "cloud_sync", "Sincronização em nuvem", "Fila offline com OneDrive ou Google Drive."
        ),
        "cloud_protection": OrganizationFeature(
            "cloud_protection", "Proteção de credenciais", "Tokens fora do SQLite e sem exposição em logs."
        ),
        "multicloud_workspace": OrganizationFeature(
            "multicloud_workspace", "Acervo remoto multicloud",
            "Monta e compara acervos existentes sem importar ou copiar silenciosamente.",
        ),
        "digital_signature": OrganizationFeature(
            "digital_signature", "Assinatura e carimbo digital", "Assinatura criptográfica integrada ao PDF."
        ),
        "access_control": OrganizationFeature(
            "access_control", "Controle de acesso", "Papéis OWNER, ADMIN, EDITOR e VIEWER."
        ),
        "server_transport": OrganizationFeature(
            "server_transport", "Camada de transporte", "Configuração administrativa NAS, HTTPS ou LAN."
        ),
        "document_requests": OrganizationFeature(
            "document_requests", "Solicitação de documentos", "Solicitações documentais opcionais."
        ),
        "deadline_timers": OrganizationFeature(
            "deadline_timers", "Controle de prazos", "Capacidade independente para vencimentos e revisões."
        ),
        "audit_history": OrganizationFeature(
            "audit_history", "Histórico auditável", "Registro das ações administrativas e documentais."
        ),
    }

    PROFILE_NAMES = {
        "PERSONAL": "Pessoal",
        "STUDENT": "Estudante",
        "BUSINESS": "Empresarial",
        "EMPTY": "Essencial",
    }
    PROFILE_FEATURES = {
        "PERSONAL": (
            "contextual_actions", "smart_search", "indexed_filters",
            "cloud_sync", "cloud_protection", "multicloud_workspace", "audit_history",
        ),
        "STUDENT": (
            "contextual_actions", "smart_search", "indexed_filters",
            "cloud_sync", "cloud_protection", "multicloud_workspace",
            "digital_signature", "audit_history",
        ),
        "BUSINESS": (
            "contextual_actions", "smart_search", "indexed_filters", "cloud_sync",
            "cloud_protection", "digital_signature", "access_control",
            "server_transport", "document_requests", "deadline_timers", "audit_history",
        ),
        "EMPTY": ("contextual_actions", "smart_search", "indexed_filters", "audit_history"),
    }
    BUSINESS_DEFAULTS = frozenset({
        "contextual_actions", "smart_search", "indexed_filters", "cloud_protection",
        "digital_signature", "access_control", "audit_history",
    })

    def __init__(self, database=None, context=None):
        self.database = database
        self.context = context
        self.repository = (
            OrganizationFeatureSettingRepository(database=database) if database else None
        )
        self.audit = AuditService(database) if database else None

    @classmethod
    def validate_profile_code(cls, profile_code: str | None) -> str:
        code = (profile_code or "EMPTY").strip().upper()
        if code not in cls.PROFILE_FEATURES:
            raise ValueError("Perfil de recursos inválido.")
        return code

    def for_profile(self, profile_code: str | None) -> OrganizationFeatureSet:
        code = self.validate_profile_code(profile_code)
        return OrganizationFeatureSet(
            profile_code=code,
            profile_name=self.PROFILE_NAMES[code],
            features=tuple(self.FEATURES[item] for item in self.PROFILE_FEATURES[code]),
        )

    def capabilities_for_organization(self, organization) -> OrganizationFeatureSet:
        return self.for_profile(
            getattr(organization, "profile_code", None)
            or getattr(organization, "template_code", None)
        )

    def default_enabled_codes(self, profile_code: str | None) -> frozenset[str]:
        profile = self.for_profile(profile_code)
        if profile.profile_code == "BUSINESS":
            return self.BUSINESS_DEFAULTS
        return profile.codes

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
