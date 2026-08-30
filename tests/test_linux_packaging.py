from pathlib import Path
from xml.etree import ElementTree

import pytest

from app.system.resources import resource_path, resource_root
from app.version import __version__, debian_version


ROOT = Path(__file__).resolve().parents[1]


def test_public_and_debian_versions_are_consistent():
    assert __version__ == "0.9.0-beta.4"
    assert debian_version() == "0.9.0~beta4"


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


def test_desktop_launcher_has_complete_xdg_contract():
    desktop = (
        ROOT / "packaging/debian/usr/share/applications/smartfile.desktop"
    ).read_text(encoding="utf-8")
    expected = (
        "Type=Application",
        "Name=SmartFile",
        "GenericName=Gerenciador de Documentos",
        "Exec=smartfile",
        "Icon=smartfile",
        "Terminal=false",
        "Categories=Office;Utility;",
        "StartupNotify=true",
    )
    assert all(item in desktop for item in expected)
    assert "StartupWMClass=" not in desktop


def test_linux_wrapper_uses_absolute_bundle_and_forwards_arguments():
    wrapper = (ROOT / "packaging/debian/usr/bin/smartfile").read_text(
        encoding="utf-8"
    )
    assert "exec /opt/smartfile/smartfile \"$@\"" in wrapper
    assert "cd " not in wrapper
    assert "PYTHONPATH" not in wrapper


def test_application_identity_matches_desktop_file():
    startup = (ROOT / "run.py").read_text(encoding="utf-8")
    assert 'app.setApplicationName("SmartFile")' in startup
    assert 'app.setApplicationDisplayName("SmartFile")' in startup
    assert 'app.setDesktopFileName("smartfile")' in startup


def test_appstream_metadata_identifies_desktop_launcher_and_beta():
    metadata = (
        ROOT
        / "packaging/debian/usr/share/metainfo"
        / "io.github.boente66.SmartFile.metainfo.xml"
    )
    component = ElementTree.parse(metadata).getroot()
    assert component.attrib["type"] == "desktop-application"
    assert component.findtext("id") == "io.github.boente66.SmartFile"
    assert component.findtext("project_license") == "MIT"
    assert component.findtext("launchable") == "smartfile.desktop"
    assert component.find("launchable").attrib["type"] == "desktop-id"
    release = component.find("./releases/release")
    assert release is not None
    assert release.attrib == {
        "version": "0.9.0-beta.4",
        "date": "2026-08-30",
        "type": "development",
    }


def test_package_control_keeps_heavy_integrations_optional():
    control = (ROOT / "packaging/debian/DEBIAN/control.in").read_text(
        encoding="utf-8"
    )
    depends = next(line for line in control.splitlines() if line.startswith("Depends:"))
    recommends = next(
        line for line in control.splitlines() if line.startswith("Recommends:")
    )
    suggests = next(
        line for line in control.splitlines() if line.startswith("Suggests:")
    )
    assert "libc6" in depends
    assert "libegl1" in depends
    assert recommends == "Recommends: libsecret-1-0"
    assert all(
        package in suggests
        for package in ("sane-utils", "libsane1", "poppler-utils", "libreoffice")
    )


def test_package_scripts_never_remove_user_directories():
    scripts = [
        ROOT / "packaging/debian/DEBIAN/postinst",
        ROOT / "packaging/debian/DEBIAN/prerm",
        ROOT / "packaging/debian/DEBIAN/postrm",
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in scripts)
    assert ".local/share/SmartFile" not in contents
    assert "rm -rf" not in contents


def test_linux_bundle_includes_system_credential_vault_backends():
    spec = (ROOT / "packaging/pyinstaller/smartfile.spec").read_text(
        encoding="utf-8"
    )
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert 'collect_submodules("keyring.backends")' in spec
    assert '"keyring"' in spec
    assert "keyring>=" in requirements


def test_linux_build_validates_package_format_desktop_and_appstream():
    build = (ROOT / "scripts/build_linux_deb.sh").read_text(encoding="utf-8")
    assert "file \"$RELEASE_DIR/$ARTIFACT\"" in build
    assert "dpkg-deb --info" in build
    assert "dpkg-deb --contents" in build
    assert "desktop-file-validate" in build
    assert "validate_appstream" in build
    assert "appstreamcli validate --help" in build
    assert "arguments+=(--strict)" in build
    assert "diagnostic_smoke_test" in build
    assert "startup_smoke_test" in build
    assert "LINTIAN_STATUS=${PIPESTATUS[0]}" in build
    assert "o relatório foi preservado" in build
    assert "cd /tmp" in build
    assert "env -u PYTHONPATH -u PYTHONHOME -u VIRTUAL_ENV" in build
    assert "scripts/audit_linux_abi.sh" in build
    assert '"${SMARTFILE_MAX_GLIBC:-2.35}"' in build
    assert '"${SMARTFILE_MAX_GLIBCXX:-3.4.29}"' in build


def test_linux_abi_audit_has_explicit_ubuntu_2204_baseline():
    audit = (ROOT / "scripts/audit_linux_abi.sh").read_text(encoding="utf-8")
    assert 'MAX_GLIBC="${2:-2.35}"' in audit
    assert 'MAX_GLIBCXX="${3:-3.4.29}"' in audit
    assert "readelf --dyn-syms --wide" in audit
    assert "MAX_REQUIRED_GLIBC=" in audit
    assert "MAX_REQUIRED_GLIBCXX=" in audit
    assert "acima da baseline" in audit


def test_installed_package_check_covers_real_entry_points():
    check = (ROOT / "scripts/test_installed_linux_package.sh").read_text(
        encoding="utf-8"
    )
    assert "dpkg-query -W" in check
    assert 'WRAPPER="/usr/bin/smartfile"' in check
    assert 'BINARY="/opt/smartfile/smartfile"' in check
    assert 'DESKTOP_FILE="/usr/share/applications/smartfile.desktop"' in check
    assert "desktop_exec" in check
    assert "cd /tmp" in check
    assert '"$command_path" --smoke-test' in check
    assert "run_persistent_startup_smoke" in check
    assert 'run_persistent_startup_smoke "$BINARY"' in check
    assert 'run_persistent_startup_smoke "$WRAPPER"' in check


def test_linux_ci_installs_reinstalls_and_removes_real_package():
    workflow = (ROOT / ".github/workflows/build-linux-deb.yml").read_text(
        encoding="utf-8"
    )
    assert "install-test:" in workflow
    assert "runs-on: ubuntu-22.04" in workflow
    assert "os: [ubuntu-22.04, ubuntu-24.04]" in workflow
    assert "runs-on: ${{ matrix.os }}" in workflow
    assert "sudo apt-get install -y \"$PWD/$package\"" in workflow
    assert "dpkg-query -W" in workflow
    assert "./scripts/test_installed_linux_package.sh" in workflow
    assert "sudo apt-get install --reinstall -y" in workflow
    assert "sudo apt-get remove -y smartfile" in workflow
    assert "package-removal-preserves-user-data" in workflow
    assert '--repo "${GITHUB_REPOSITORY}"' in workflow


def test_linux_package_templates_do_not_contain_credentials():
    paths = [
        ROOT / "packaging/debian/DEBIAN/control.in",
        ROOT / "packaging/debian/usr/bin/smartfile",
        ROOT / "packaging/debian/usr/share/applications/smartfile.desktop",
        ROOT
        / "packaging/debian/usr/share/metainfo"
        / "io.github.boente66.SmartFile.metainfo.xml",
    ]
    contents = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "access_token" not in contents
    assert "refresh_token" not in contents
    assert "client_secret" not in contents
