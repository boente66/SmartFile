from __future__ import annotations

from app.entities.tag_entity import TagEntity
from app.repositories.base_repository import BaseRepository


class TagRepository(BaseRepository):
    def create(self, entity: TagEntity) -> TagEntity:
        cursor = self._write(
            "INSERT INTO tags (name, created_at) VALUES (?, ?)",
            (entity.name, entity.created_at),
        )
        entity.id = cursor.lastrowid
        return entity

    def delete(self, tag_id: int) -> bool:
        return self._write("DELETE FROM tags WHERE id = ?", (tag_id,)).rowcount > 0

    def find_by_id(self, tag_id: int) -> TagEntity | None:
        row = self._fetch_one("SELECT * FROM tags WHERE id = ?", (tag_id,))
        return self._row(row) if row else None

    def find_all(self) -> list[TagEntity]:
        return [self._row(row) for row in self._fetch_all("SELECT * FROM tags ORDER BY name")]

    @staticmethod
    def _row(row) -> TagEntity:
        return TagEntity(**dict(row))
