from __future__ import annotations

from datetime import datetime, timezone

from app.entities.document_request_entity import DocumentRequestEntity
from app.repositories.document_request_repository import DocumentRequestRepository
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.audit_service import AuditService
from app.services.organization_feature_service import OrganizationFeatureService
from app.services.organization_service import OrganizationService


class DocumentRequestService:
    STATUSES = {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED", "OVERDUE"}

    def __init__(self, database, context):
        self.context = context
        self.database = database
        self.repository = DocumentRequestRepository(database=database)
        self.members = OrganizationMemberRepository(database=database)
        self.users = UserRepository(database=database)
        self.organizations = OrganizationService(database)
        self.features = OrganizationFeatureService(database)
        self.audit = AuditService(database)

    def list_requests(self, organization_id: int) -> list[DocumentRequestEntity]:
        self._require(organization_id, "document.request.view")
        if self.deadline_enabled(organization_id):
            self.repository.mark_overdue(organization_id, self._now())
        return self.repository.find_by_organization(organization_id)

    def list_assignable_members(self, organization_id: int):
        self._require(organization_id, "document.request.view")
        users = []
        for membership in self.members.find_by_organization(organization_id, active_only=True):
            user = self.users.find_by_id(membership.user_id)
            if user is not None and user.is_active:
                users.append(user)
        return sorted(users, key=lambda user: user.display_name.casefold())

    def can_create(self) -> bool:
        return self.context.has_permission("document.request.create")

    def can_update(self) -> bool:
        return self.context.has_permission("document.request.update")

    def deadline_enabled(self, organization_id: int) -> bool:
        organization = self.organizations.repository.find_by_id(organization_id)
        return bool(organization and self.features.for_organization(organization).has("deadline_timers"))

    def create(
        self, organization_id: int, title: str, description: str | None = None,
        assigned_to_user_id: int | None = None, due_at: str | None = None,
    ) -> DocumentRequestEntity:
        self._require(organization_id, "document.request.create")
        clean_title = " ".join(title.split())
        if not clean_title:
            raise ValueError("Informe o documento solicitado.")
        if len(clean_title) > 180:
            raise ValueError("O título deve possuir até 180 caracteres.")
        self._validate_assignee(organization_id, assigned_to_user_id)
        if due_at:
            organization = self.organizations.repository.find_by_id(organization_id)
            self.features.require(organization, "deadline_timers")
            try:
                parsed_due = datetime.fromisoformat(due_at)
                if parsed_due.tzinfo is None:
                    parsed_due = parsed_due.replace(tzinfo=timezone.utc)
                due_at = parsed_due.astimezone(timezone.utc).isoformat()
            except ValueError as exc:
                raise ValueError("Informe um prazo válido.") from exc
            if due_at <= self._now():
                raise ValueError("O prazo deve estar no futuro.")
        now = self._now()
        created = self.repository.create(DocumentRequestEntity(
            organization_id=organization_id, title=clean_title,
            description=(description or "").strip() or None,
            requested_by_user_id=self.context.current_user.id,
            assigned_to_user_id=assigned_to_user_id, due_at=due_at,
            created_at=now, updated_at=now,
        ))
        self.audit.record(
            "DOCUMENT_REQUEST_CREATED", user_id=self.context.current_user.id,
            organization_id=organization_id, target_type="document_request",
            target_id=created.id, description=f"Solicitação criada: {clean_title}",
        )
        return created

    def set_status(self, organization_id: int, request_id: int, status: str) -> None:
        self._require(organization_id, "document.request.update")
        value = status.strip().upper()
        if value not in self.STATUSES:
            raise ValueError("Estado de solicitação inválido.")
        now = self._now()
        if not self.repository.update_status(
            request_id, organization_id, value, now,
            now if value == "COMPLETED" else None,
        ):
            raise ValueError("Solicitação não encontrada.")
        self.audit.record(
            "DOCUMENT_REQUEST_STATUS_CHANGED", user_id=self.context.current_user.id,
            organization_id=organization_id, target_type="document_request",
            target_id=request_id, description=f"Estado alterado para {value}",
        )

    def _require(self, organization_id: int, permission: str) -> None:
        if organization_id != getattr(self.context.active_organization, "id", None):
            raise PermissionError("Ative a organização antes de acessar solicitações.")
        self.context.require_permission(permission)
        organization = self.organizations.repository.find_by_id(organization_id)
        self.features.require(organization, "document_requests")

    def _validate_assignee(
        self, organization_id: int, assigned_to_user_id: int | None,
    ) -> None:
        if assigned_to_user_id is None:
            return
        user = self.users.find_by_id(int(assigned_to_user_id))
        if user is None:
            raise ValueError("O responsável selecionado não existe.")
        if not user.is_active:
            raise ValueError("O responsável selecionado está inativo.")
        membership = self.members.find(organization_id, int(assigned_to_user_id))
        if membership is None or membership.status != "ACTIVE":
            raise ValueError("O responsável deve ser membro ativo da organização.")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
