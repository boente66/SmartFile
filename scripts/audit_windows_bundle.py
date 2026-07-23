"""Auditoria determinística do bundle Windows antes da publicação."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


FORBIDDEN_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".log", ".pfx", ".p12", ".pem", ".key",
}
FORBIDDEN_NAMES = {
    ".git", "venv", ".venv", "__pycache__", "storage", "tokens", "cache",
}
TEXT_SUFFIXES = {".cfg", ".ini", ".json", ".md", ".qss", ".sql", ".txt", ".xml"}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)(?:access|refresh)[_-]?token\s*[:=]\s*[\"'][^\"']{16,}"),
    re.compile(r"(?i)client[_-]?secret\s*[:=]\s*[\"'][^\"']{8,}"),
    re.compile(r"(?i)(?:/home/[^/\s]+/|C:\\Users\\[^\\\s]+\\)"),
)


def audit_bundle(root: Path) -> list[str]:
    errors: list[str] = []
    required = (
        root / "SmartFile.exe",
        root / "_internal" / "assets" / "style.qss",
        root / "_internal" / "assets" / "icons" / "app.svg",
        root / "_internal" / "app" / "database" / "schema.sql",
        root / "_internal" / "PyQt6" / "Qt6" / "plugins" / "platforms" / "qwindows.dll",
    )
    for path in required:
        if not path.is_file():
            errors.append(f"Recurso obrigatório ausente: {path.relative_to(root)}")

    for path in root.rglob("*"):
        relative = path.relative_to(root)
        lowered_parts = {part.lower() for part in relative.parts}
        if lowered_parts & FORBIDDEN_NAMES:
            errors.append(f"Diretório proibido no bundle: {relative}")
        if not path.is_file():
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"Arquivo sensível no bundle: {relative}")
        if "app/cloud/resources" in relative.as_posix().lower():
            errors.append(f"Configuração OAuth pessoal no bundle: {relative}")
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"Conteúdo sensível detectado: {relative}")
                break
    return sorted(set(errors))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    if not root.is_dir():
        raise SystemExit(f"Bundle inexistente: {root}")
    errors = audit_bundle(root)
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Bundle Windows auditado com sucesso: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
