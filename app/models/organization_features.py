from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OrganizationFeature:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class OrganizationFeatureSet:
    profile_code: str
    profile_name: str
    features: tuple[OrganizationFeature, ...]

    def has(self, code: str) -> bool:
        return any(feature.code == code for feature in self.features)

    @property
    def codes(self) -> frozenset[str]:
        return frozenset(feature.code for feature in self.features)


class OrganizationFeatureCatalog:
    """Catálogo puro compartilhado; não consulta banco nem aplica autorização."""

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
