# -*- mode: python ; coding: utf-8 -*-
"""Bundle Windows x64 onedir do SmartFile."""

from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

project_root = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "app" / "database" / "schema.sql"), "app/database"),
    (str(project_root / "LICENSE"), "."),
    (str(project_root / "docs" / "RELEASE_NOTES_0.9.0-beta.1.md"), "docs"),
    (str(project_root / "docs" / "GUIA_TESTE_WINDOWS_BETA.md"), "docs"),
]

# Somente módulos carregados dinamicamente pela aplicação.
hiddenimports = [
    "google_auth_oauthlib.flow",
    "keyring.backends.Windows",
    "keyring.backends.chainer",
    "keyring.backends.null",
    "msal",
]
if find_spec("twain") is not None:
    hiddenimports.append("twain")

metadata = []
for distribution in (
    "PyMuPDF",
    "pyHanko",
    "pyhanko-certvalidator",
    "keyring",
    "msal",
    "google-auth-oauthlib",
    "pytwain",
):
    try:
        metadata += copy_metadata(distribution)
    except Exception:
        # Nem todas as versões consultam metadata em tempo de execução.
        pass

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas + metadata,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6", "tkinter", "sane", "pytest", "_pytest"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SmartFile",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(project_root / "assets" / "icons" / "app.ico"),
    version=str(project_root / "packaging" / "windows" / "version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SmartFile",
)
