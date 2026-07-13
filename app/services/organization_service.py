from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone

from app.database.database import Database
from app.entities.organization_entity import OrganizationEntity
from app.repositories.organization_repository import OrganizationRepository


class OrganizationService:
    def __init__(self, database: Database):
        self.database = database
        self.repository = OrganizationRepository(database=database)
        default = self.repository.find_default()
        if default is None or default.id is None:
            raise RuntimeError("A organização padrão não foi inicializada.")
        persisted_id = self.repository.get_active_id()
        persisted = self.repository.find_by_id(persisted_id) if persisted_id else None
        self._active_id = (
            persisted.id
            if persisted is not None and persisted.status == "ACTIVE" and persisted.id is not None
            else default.id
        )
        self.repository.set_active_id(self._active_id)

    @property
    def active_id(self) -> int:
        return self._active_id

    def active(self) -> OrganizationEntity:
        entity = self.repository.find_by_id(self._active_id)
        if entity is None or entity.status != "ACTIVE":
            raise ValueError("A organização ativa não está disponível.")
        return entity

    def list_organizations(self) -> list[OrganizationEntity]:
        return self.repository.find_all()

    def create(self, name: str, description: str | None = None) -> OrganizationEntity:
        clean_name = self._name(name)
        slug = self._unique_slug(clean_name)
        now = self._now()
        return self.repository.create(
            OrganizationEntity(
                name=clean_name, description=description or None, slug=slug,
                created_at=now, updated_at=now,
            )
        )

    def update(self, organization_id: int, name: str, description: str | None = None) -> OrganizationEntity:
        entity = self._active_entity(organization_id)
        entity.name = self._name(name)
        entity.description = description or None
        entity.slug = self._unique_slug(entity.name, entity.id)
        entity.updated_at = self._now()
        return self.repository.update(entity)

    def delete(self, organization_id: int) -> bool:
        entity = self._active_entity(organization_id)
        if entity.is_default:
            raise ValueError("A organização padrão não pode ser excluída.")
        changed = self.repository.delete(organization_id, self._now())
        if changed and self._active_id == organization_id:
            default = self.repository.find_default()
            if default and default.id:
                self._active_id = default.id
                self.repository.set_active_id(self._active_id)
        return changed

    def set_active(self, organization_id: int) -> OrganizationEntity:
        entity = self._active_entity(organization_id)
        self._active_id = organization_id
        self.repository.set_active_id(organization_id)
        return entity

    def _active_entity(self, organization_id: int) -> OrganizationEntity:
        entity = self.repository.find_by_id(organization_id)
        if entity is None or entity.status != "ACTIVE":
            raise ValueError("Organização não encontrada.")
        return entity

    def _unique_slug(self, name: str, current_id: int | None = None) -> str:
        base = self._slug(name) or "organizacao"
        candidate = base
        suffix = 2
        while True:
            existing = self.repository.find_by_slug(candidate)
            if existing is None or existing.id == current_id:
                return candidate
            candidate = f"{base}-{suffix}"
            suffix += 1

    @staticmethod
    def _name(name: str) -> str:
        clean = name.strip()
        if not clean:
            raise ValueError("Informe o nome da organização.")
        if len(clean) > 100:
            raise ValueError("O nome da organização deve ter até 100 caracteres.")
        return clean

    @staticmethod
    def _slug(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
