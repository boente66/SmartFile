# -*- mode: python ; coding: utf-8 -*-
"""Bundle Linux onedir do SmartFile."""

from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

project_root = Path(SPECPATH).resolve().parents[1]

datas = [
    (str(project_root / "assets"), "assets"),
    (str(project_root / "app" / "database" / "schema.sql"), "app/database"),
]

hiddenimports = [
    "google_auth_oauthlib.flow",
    "msal",
]
hiddenimports += collect_submodules("keyring.backends")
if find_spec("sane") is not None:
    hiddenimports.append("sane")

metadata = []
for distribution in (
    "PyMuPDF",
    "pyHanko",
    "pyhanko-certvalidator",
    "keyring",
    "msal",
    "google-auth-oauthlib",
):
    try:
        metadata += copy_metadata(distribution)
    except Exception:
        # Algumas versões não consultam metadata em runtime.
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
    excludes=[
        "PySide6", "tkinter", "twain", "win32api", "win32ui", "pytest", "_pytest",
    ],
    noarchive=False,
    optimize=1,
)
# A wheel PyQt6 usada no Ubuntu 24.04 traz um plugin TIFF ligado à antiga
# libtiff.so.5. O SmartFile processa TIFF pelo Pillow; manter esse plugin
# inutilizável criaria uma dependência impossível em sistemas atuais.
a.binaries = [
    item for item in a.binaries
    if not item[0].endswith("PyQt6/Qt6/plugins/imageformats/libqtiff.so")
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="smartfile",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SmartFile",
)
