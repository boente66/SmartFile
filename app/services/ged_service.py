from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".jpg",
    ".jpeg",
    ".png",
    ".tiff",
    ".bmp",
}


def list_documents(folder: str | Path, search: str = "") -> list[dict[str, Any]]:
    """Lista arquivos de documento em uma pasta, com metadados básicos."""

    root = Path(folder)
    if not root.exists() or not root.is_dir():
        return []

    query = search.strip().lower()
    documents: list[dict[str, Any]] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        extension = path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            continue

        if query and query not in path.name.lower():
            continue

        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%d/%m/%Y %H:%M")

        documents.append(
            {
                "name": path.name,
                "path": str(path),
                "extension": extension,
                "size": _format_size(stat.st_size),
                "modified": modified,
                "kind": _describe_kind(path),
            }
        )

    return documents


def rename_document(path: str | Path, new_name: str) -> Path:
    """Renomeia um documento preservando a extensão, se necessário."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {source}")

    if not new_name or "/" in new_name or "\\" in new_name:
        raise ValueError("Informe um nome válido para o arquivo.")

    if source.suffix and not Path(new_name).suffix:
        new_name = f"{new_name}{source.suffix}"

    target = source.with_name(new_name)
    if target.exists() and target != source:
        raise FileExistsError(f"Já existe um arquivo chamado {new_name}")

    return source.rename(target)


def delete_document(path: str | Path) -> None:
    """Remove um arquivo documentado."""

    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {source}")

    source.unlink()


def _format_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit != "B" else f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.0f} GB"


def _describe_kind(path: Path) -> str:
    extension = path.suffix.lower()
    if extension == ".pdf":
        return "PDF"
    if extension in {".docx", ".doc"}:
        return "Documento"
    if extension in {".xlsx", ".xls", ".csv"}:
        return "Planilha"
    if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
        return "Imagem"
    return "Texto"
