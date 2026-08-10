from __future__ import annotations

import json
from uuid import uuid4

from app.errors.transport_exceptions import (
    CredentialInUseError,
    CredentialNotFoundError,
)
from app.models.transport_credential import TransportCredential
from app.repositories.transport_target_repository import TransportTargetRepository
from app.security.credential_provider import CredentialProvider, OSCredentialProvider


class CredentialVaultService:
    """Gerencia referências opacas e autorização do cofre de transporte."""

    def __init__(self, database, context, provider: CredentialProvider | None = None):
        self.context = context
        self.provider = provider or OSCredentialProvider()
        self.targets = TransportTargetRepository(database=database)

    def store(
        self, organization_id: int, credential: TransportCredential,
    ) -> str:
        self._require(organization_id)
        username = credential.username.strip()
        if not username or not credential.password:
            raise ValueError("Informe usuário e senha da credencial.")
        reference = f"smartfile:transport:{organization_id}:{uuid4()}"
        payload = json.dumps(
            {"username": username, "password": credential.password},
            ensure_ascii=False,
        )
        self.provider.store(reference, payload)
        return reference

    def get(
        self, organization_id: int, reference: str,
    ) -> TransportCredential:
        self._require(organization_id)
        self._validate_reference(organization_id, reference)
        payload = self.provider.get(reference)
        if payload is None:
            raise CredentialNotFoundError("Credencial de transporte não encontrada.")
        try:
            values = json.loads(payload)
            username = str(values["username"])
            password = str(values["password"])
        except (KeyError, TypeError, ValueError):
            raise CredentialNotFoundError(
                "A credencial de transporte armazenada está inválida."
            ) from None
        return TransportCredential(username=username, password=password)

    def exists(self, organization_id: int, reference: str | None) -> bool:
        self._require(organization_id)
        if not reference:
            return False
        self._validate_reference(organization_id, reference)
        return self.provider.exists(reference)

    def delete(self, organization_id: int, reference: str) -> None:
        self._require(organization_id)
        self._validate_reference(organization_id, reference)
        if self.targets.is_credential_in_use(organization_id, reference):
            raise CredentialInUseError(
                "A credencial ainda é utilizada por um destino ou job histórico."
            )
        self.provider.delete(reference)

    def delete_if_unused(self, organization_id: int, reference: str | None) -> bool:
        self._require(organization_id)
        if not reference:
            return False
        self._validate_reference(organization_id, reference)
        if self.targets.is_credential_in_use(organization_id, reference):
            return False
        self.provider.delete(reference)
        return True

    def discard_compensation(self, organization_id: int, reference: str) -> None:
        """Remove segredo recém-criado quando a transação de banco falha."""
        self._validate_reference(organization_id, reference)
        self.provider.delete(reference)

    def _require(self, organization_id: int) -> None:
        if organization_id != getattr(self.context.active_organization, "id", None):
            raise PermissionError("Ative a organização antes de gerenciar credenciais.")
        self.context.require_permission("transport.configure")

    @staticmethod
    def _validate_reference(organization_id: int, reference: str) -> None:
        prefix = f"smartfile:transport:{organization_id}:"
        if not reference.startswith(prefix) or len(reference) <= len(prefix):
            raise PermissionError("A credencial não pertence à organização ativa.")
