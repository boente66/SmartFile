from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TransportCredential:
    """Credencial transitória; nunca deve ser persistida no SQLite."""

    username: str
    password: str
