from pathlib import Path

import pytest

from app.system.resources import resource_path, resource_root
from app.version import __version__, debian_version


ROOT = Path(__file__).resolve().parents[1]


def test_public_and_debian_versions_are_consistent():
    assert __version__ == "0.9.0-beta.1"
    assert debian_version() == "0.9.0~beta1"


def test_resource_resolution_uses_project_root_in_source_mode():
    assert resource_root() == ROOT
    assert resource_path("assets/style.qss").is_file()
    assert resource_path("assets/icons/app.svg").is_file()
    assert resource_path("app/database/schema.sql").is_file()


@pytest.mark.parametrize("unsafe", ["../LICENSE", "/etc/passwd"])
def test_resource_resolution_rejects_unsafe_paths(unsafe):
    with pytest.raises(ValueError):
        resource_path(unsafe)


def test_debian_integration_does_not_claim_pdf_mime_association():
    desktop = (
        ROOT / "packaging/debian/usr/share/applications/smartfile.desktop"
    ).read_text(encoding="utf-8")
    assert "Exec=smartfile" in desktop
    assert "MimeType=" not in desktop


def test_package_scripts_never_remove_user_directories():
    scripts = [
        ROOT / "packaging/debian/DEBIAN/postinst",
        ROOT / "packaging/debian/DEBIAN/prerm",
        ROOT / "packaging/debian/DEBIAN/postrm",
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
    assert ".local/share/SmartFile" not in contents
    assert "rm -rf" not in contents
