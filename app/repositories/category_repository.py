from __future__ import annotations

from app.entities.category_entity import CategoryEntity
from app.repositories.base_repository import BaseRepository


class CategoryRepository(BaseRepository):
    def create(self, entity: CategoryEntity) -> CategoryEntity:
        cursor = self._write(
            "INSERT INTO categories (name, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (entity.name, entity.description, entity.created_at, entity.updated_at),
        )
        entity.id = cursor.lastrowid
        return entity

    def update(self, entity: CategoryEntity) -> CategoryEntity:
        self._write(
            "UPDATE categories SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (entity.name, entity.description, entity.updated_at, entity.id),
        )
        return entity

    def delete(self, category_id: int) -> bool:
        return self._write("DELETE FROM categories WHERE id = ?", (category_id,)).rowcount > 0

    def find_by_id(self, category_id: int) -> CategoryEntity | None:
        row = self._fetch_one("SELECT * FROM categories WHERE id = ?", (category_id,))
        return self._row(row) if row else None

    def find_all(self) -> list[CategoryEntity]:
        return [self._row(row) for row in self._fetch_all("SELECT * FROM categories ORDER BY name")]

    @staticmethod
    def _row(row) -> CategoryEntity:
        return CategoryEntity(**dict(row))
