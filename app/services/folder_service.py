from __future__ import annotations

from datetime import datetime, timezone

from app.database.database import Database
from app.entities.folder_entity import FolderEntity
from app.repositories.folder_repository import FolderRepository


class FolderService:
    def __init__(self, database: Database):
        self.repository = FolderRepository(database=database)

    def list_folders(self, organization_id: int) -> list[FolderEntity]:
        return self.repository.find_all(organization_id)

    def create(self, organization_id: int, name: str, parent_id: int | None = None) -> FolderEntity:
        clean = self._name(name)
        if parent_id is not None:
            parent = self.repository.find_by_id(parent_id, organization_id)
            if parent is None or parent.status != "ACTIVE":
                raise ValueError("A pasta pai não pertence à organização ativa.")
        now = self._now()
        return self.repository.create(
            FolderEntity(
                organization_id=organization_id, parent_id=parent_id, name=clean,
                created_at=now, updated_at=now,
            )
        )

    def rename(self, organization_id: int, folder_id: int, name: str) -> FolderEntity:
        entity = self._folder(organization_id, folder_id)
        entity.name = self._name(name)
        entity.updated_at = self._now()
        return self.repository.update(entity)

    def move(self, organization_id: int, folder_id: int, parent_id: int | None) -> FolderEntity:
        entity = self._folder(organization_id, folder_id)
        if parent_id == folder_id:
            raise ValueError("Uma pasta não pode ser movida para ela mesma.")
        if parent_id is not None:
            parent = self._folder(organization_id, parent_id)
            ancestor = parent
            while ancestor.parent_id is not None:
                if ancestor.parent_id == folder_id:
                    raise ValueError("Não é possível mover uma pasta para uma subpasta própria.")
                ancestor = self._folder(organization_id, ancestor.parent_id)
        entity.parent_id = parent_id
        entity.updated_at = self._now()
        return self.repository.update(entity)

    def delete(self, organization_id: int, folder_id: int) -> bool:
        self._folder(organization_id, folder_id)
        return self.repository.delete(folder_id, organization_id, self._now())

    def _folder(self, organization_id: int, folder_id: int) -> FolderEntity:
        entity = self.repository.find_by_id(folder_id, organization_id)
        if entity is None or entity.status != "ACTIVE":
            raise ValueError("Pasta não encontrada na organização ativa.")
        return entity

    @staticmethod
    def _name(name: str) -> str:
        clean = " ".join(name.split())
        if not clean:
            raise ValueError("Informe o nome da pasta.")
        if len(clean) > 120:
            raise ValueError("O nome da pasta deve ter até 120 caracteres.")
        return clean

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
