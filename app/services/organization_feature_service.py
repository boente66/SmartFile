from __future__ import annotations

from app.models.organization_features import OrganizationFeature, OrganizationFeatureSet


class OrganizationFeatureService:
    """Política central de capacidades; templates cuidam somente das pastas iniciais."""

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
            "document_requests", "Solicitação de documentos", "Solicitações com responsável, prazo e estado."
        ),
        "deadline_timers": OrganizationFeature(
            "deadline_timers", "Temporizadores", "Acompanhamento de vencimentos e atrasos."
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
            "cloud_sync", "cloud_protection", "audit_history",
        ),
        "STUDENT": (
            "contextual_actions", "smart_search", "indexed_filters",
            "cloud_sync", "cloud_protection", "digital_signature", "audit_history",
        ),
        "BUSINESS": tuple(FEATURES),
        "EMPTY": ("contextual_actions", "smart_search", "indexed_filters", "audit_history"),
    }

    def for_profile(self, profile_code: str | None) -> OrganizationFeatureSet:
        code = (profile_code or "EMPTY").strip().upper()
        if code not in self.PROFILE_FEATURES:
            code = "EMPTY"
        return OrganizationFeatureSet(
            profile_code=code,
            profile_name=self.PROFILE_NAMES[code],
            features=tuple(self.FEATURES[item] for item in self.PROFILE_FEATURES[code]),
        )

    def for_organization(self, organization) -> OrganizationFeatureSet:
        return self.for_profile(
            getattr(organization, "profile_code", None)
            or getattr(organization, "template_code", None)
        )

    def require(self, organization, feature_code: str) -> None:
        if not self.for_organization(organization).has(feature_code):
            raise PermissionError("Este recurso não está disponível no perfil da organização.")
