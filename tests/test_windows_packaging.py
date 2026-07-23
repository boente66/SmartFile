from pathlib import Path

from app.system.app_paths import AppPaths
from scripts.audit_windows_bundle import audit_bundle


ROOT = Path(__file__).resolve().parents[1]


def test_windows_paths_use_appdata_without_writing_program_files(monkeypatch, tmp_path):
    local = tmp_path / "Local"
    roaming = tmp_path / "Roaming"
    monkeypatch.setattr("app.system.app_paths.sys.platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(roaming))

    paths = AppPaths()

    assert paths.data_dir == (local / "SmartFile").resolve()
    assert paths.config == (roaming / "SmartFile").resolve()
    assert "Program Files" not in str(paths.data_dir)


def test_windows_pyinstaller_spec_is_onedir_and_bundles_required_resources():
    spec = (ROOT / "packaging/pyinstaller/smartfile_windows.spec").read_text(
        encoding="utf-8"
    )

    assert 'name="SmartFile"' in spec
    assert "exclude_binaries=True" in spec
    assert "COLLECT(" in spec
    assert '"assets"' in spec
    assert '"schema.sql"' in spec
    assert '"app.ico"' in spec
    assert '"sane"' in spec
    assert (ROOT / "assets/icons/app.ico").is_file()


def test_inno_installer_preserves_user_data_and_does_not_associate_files():
    script = (ROOT / "packaging/windows/smartfile.iss").read_text(encoding="utf-8")

    assert "DefaultDirName={autopf}\\SmartFile" in script
    assert "UninstallDisplayIcon=" in script
    assert "desktopicon" in script
    assert "ChangesAssociations=no" in script
    assert "ChangesEnvironment=no" in script
    assert "[UninstallDelete]" not in script
    assert "runasoriginaluser" in script


def test_windows_workflow_builds_expected_artifacts_without_publishing_release():
    workflow = (ROOT / ".github/workflows/build-windows.yml").read_text(
        encoding="utf-8"
    )

    assert "runs-on: windows-latest" in workflow
    assert "python-version: '3.12'" in workflow
    assert "workflow_dispatch:" in workflow
    assert "SmartFile-$env:SMARTFILE_VERSION-Windows-x64-Setup.exe" in workflow
    assert "SmartFile-$env:SMARTFILE_VERSION-Windows-x64-Portable.zip" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "gh release create" not in workflow


def test_bundle_audit_rejects_mutable_database(tmp_path):
    bundle = tmp_path / "SmartFile"
    required = (
        bundle / "SmartFile.exe",
        bundle / "_internal/assets/style.qss",
        bundle / "_internal/assets/icons/app.svg",
        bundle / "_internal/app/database/schema.sql",
        bundle / "_internal/PyQt6/Qt6/plugins/platforms/qwindows.dll",
    )
    for path in required:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"placeholder")

    assert audit_bundle(bundle) == []

    (bundle / "_internal/smartfile.db").write_bytes(b"not allowed")

    assert any("smartfile.db" in error for error in audit_bundle(bundle))
