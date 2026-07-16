"""Resolução centralizada de recursos somente leitura da aplicação."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    """Retorna a raiz dos recursos no código-fonte ou no bundle PyInstaller."""

    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parents[2]


def resource_path(relative_path: str | Path) -> Path:
    """Resolve um caminho relativo sem permitir fuga da raiz de recursos."""

    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("O caminho do recurso deve ser relativo e seguro.")
    root = resource_root()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("O recurso solicitado está fora da aplicação.")
    return candidate
