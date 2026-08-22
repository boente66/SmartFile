from __future__ import annotations

import pytest

from app.services.application_update_service import ApplicationUpdateService
from app.workers.application_update_worker import ApplicationUpdateWorker


def _release(version="0.9.0-beta.3", prerelease=True):
    return {
        "tag_name": f"v{version}",
        "draft": False,
        "prerelease": prerelease,
        "html_url": f"https://github.com/boente66/SmartFile/releases/tag/v{version}",
        "assets": [
            {
                "name": f"smartfile_{version.replace('-', '.')}_amd64.deb",
                "browser_download_url": f"https://github.com/boente66/SmartFile/releases/download/v{version}/smartfile_amd64.deb",
            },
            {
                "name": f"SmartFile-{version}-Windows-x64-Setup.exe",
                "browser_download_url": f"https://github.com/boente66/SmartFile/releases/download/v{version}/SmartFile-Setup.exe",
            },
        ],
        "body": "Correções de estabilidade.",
    }


@pytest.mark.parametrize(
    ("system", "machine", "suffix"),
    [("Linux", "x86_64", ".deb"), ("Windows", "AMD64", ".exe")],
)
def test_update_selects_installer_for_operating_system(monkeypatch, system, machine, suffix):
    monkeypatch.setattr("platform.system", lambda: system)
    monkeypatch.setattr("platform.machine", lambda: machine)
    update = ApplicationUpdateService(
        "0.9.0-beta.2", lambda _url, _timeout: [_release()]
    ).check()
    assert update is not None
    assert update.asset_name.endswith(suffix)
    assert update.download_url.startswith("https://github.com/boente66/SmartFile/")


def test_update_ignores_same_or_older_version():
    service = ApplicationUpdateService(
        "0.9.0-beta.2", lambda _url, _timeout: [_release("0.9.0-beta.2")]
    )
    assert service.check() is None


def test_stable_channel_does_not_offer_prerelease():
    service = ApplicationUpdateService(
        "1.0.0", lambda _url, _timeout: [_release("1.1.0-beta.1")]
    )
    assert service.check() is None


def test_update_rejects_untrusted_download_url(monkeypatch):
    monkeypatch.setattr("platform.system", lambda: "Linux")
    monkeypatch.setattr("platform.machine", lambda: "x86_64")
    release = _release()
    release["assets"][0]["browser_download_url"] = "https://evil.example/update.deb"
    update = ApplicationUpdateService(
        "0.9.0-beta.2", lambda _url, _timeout: [release]
    ).check()
    assert update.download_url == release["html_url"]


def test_update_worker_reports_network_failure_without_technical_details():
    service = ApplicationUpdateService(
        "0.9.0-beta.2", lambda *_args: (_ for _ in ()).throw(TimeoutError("secret"))
    )
    failures = []
    worker = ApplicationUpdateWorker(service)
    worker.failed.connect(failures.append)
    worker.run()
    assert failures == ["Não foi possível verificar atualizações agora."]
