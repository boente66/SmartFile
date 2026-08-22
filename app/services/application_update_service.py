from __future__ import annotations

import json
import platform
import re
from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.models.application_update import ApplicationUpdate


class ApplicationUpdateService:
    """Consulta releases oficiais e escolhe o instalador compatível, sem autoexecutá-lo."""

    RELEASES_API = "https://api.github.com/repos/boente66/SmartFile/releases?per_page=10"
    TIMEOUT_SECONDS = 8

    def __init__(self, current_version: str, transport: Callable | None = None):
        self.current_version = current_version
        self._transport = transport or self._request

    def check(self) -> ApplicationUpdate | None:
        releases = self._transport(self.RELEASES_API, self.TIMEOUT_SECONDS)
        if not isinstance(releases, list):
            raise ValueError("O serviço de atualização retornou uma resposta inválida.")
        current_is_beta = "beta" in self.current_version.casefold()
        candidates = []
        for release in releases:
            if not isinstance(release, dict) or release.get("draft"):
                continue
            if release.get("prerelease") and not current_is_beta:
                continue
            version = str(release.get("tag_name") or "").lstrip("vV")
            if self._version_key(version) <= self._version_key(self.current_version):
                continue
            candidates.append((self._version_key(version), version, release))
        if not candidates:
            return None
        _key, version, release = max(candidates, key=lambda item: item[0])
        _system, pattern, platform_name = self._platform_asset()
        asset = next(
            (
                item for item in release.get("assets", [])
                if isinstance(item, dict) and pattern.search(str(item.get("name", "")))
            ),
            None,
        )
        release_url = self._safe_github_url(str(release.get("html_url") or ""))
        asset_url = (
            self._safe_github_url(str(asset.get("browser_download_url") or ""))
            if asset else ""
        )
        download_url = asset_url or release_url
        if not download_url:
            raise ValueError("A release não possui um endereço oficial válido.")
        return ApplicationUpdate(
            version=version,
            platform_name=platform_name,
            download_url=download_url,
            release_url=release_url or download_url,
            asset_name=str(asset.get("name")) if asset else None,
            notes=str(release.get("body") or "")[:1200],
        )

    @staticmethod
    def _platform_asset():
        system = platform.system().casefold()
        machine = platform.machine().casefold()
        x64 = machine in {"x86_64", "amd64"}
        if system == "windows" and x64:
            return system, re.compile(r"windows.*x64.*setup\.exe$", re.I), "Windows 64 bits"
        if system == "linux" and x64:
            return system, re.compile(r"amd64\.deb$", re.I), "Linux amd64 (.deb)"
        return system, re.compile(r"$^"), f"{platform.system()} {platform.machine()}"

    @staticmethod
    def _version_key(version: str) -> tuple[int, int, int, int, int]:
        match = re.fullmatch(
            r"(\d+)\.(\d+)\.(\d+)(?:[-.]?(alpha|beta|rc)[.-]?(\d+)?)?",
            version.strip(), re.I,
        )
        if not match:
            return (0, 0, 0, 0, 0)
        stage = {"alpha": 0, "beta": 1, "rc": 2, None: 3}[match.group(4).lower() if match.group(4) else None]
        return (
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            stage, int(match.group(5) or 0),
        )

    @staticmethod
    def _safe_github_url(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
            return ""
        return value

    @staticmethod
    def _request(url: str, timeout: int):
        request = Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "SmartFile-Update-Checker",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
