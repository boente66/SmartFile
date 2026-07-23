from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from app.cloud.cloud_models import CloudAuthResult, CloudUploadRequest, RemoteMetadata
from app.cloud.cloud_provider import (
    CloudAuthenticationError,
    CloudError,
    CloudProvider,
)

logger = logging.getLogger(__name__)


class OneDriveProvider(CloudProvider):
    GRAPH = "https://graph.microsoft.com/v1.0"
    AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0"
    SCOPES = "offline_access User.Read Files.ReadWrite"
    MAX_DELTA_PAGES = 100
    DELTA_DEADLINE_SECONDS = 120

    def authenticate(self, credentials: dict[str, str]) -> CloudAuthResult:
        action = credentials.get("action", "complete")
        client_id = credentials.get("client_id", "")
        redirect_uri = credentials.get("redirect_uri", "http://localhost")
        if not client_id:
            raise CloudAuthenticationError("Configure SMARTFILE_ONEDRIVE_CLIENT_ID.")
        if action == "begin":
            verifier = secrets.token_urlsafe(64)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            query = urlencode({
                "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "response_mode": "query", "scope": self.SCOPES,
                "code_challenge": challenge, "code_challenge_method": "S256",
            })
            return CloudAuthResult(authorization_url=f"{self.AUTH}/authorize?{query}", code_verifier=verifier)
        payload = {
            "client_id": client_id, "grant_type": "authorization_code",
            "code": credentials.get("code", ""), "redirect_uri": redirect_uri,
            "scope": self.SCOPES, "code_verifier": credentials.get("code_verifier", ""),
        }
        token = self._form_request(f"{self.AUTH}/token", payload)
        self.access_token = token["access_token"]
        profile, _ = self._json_request("GET", f"{self.GRAPH}/me")
        return self._auth_result(token, profile.get("mail") or profile.get("userPrincipalName"), profile.get("displayName"))

    def refresh_token(self, refresh_token: str, credentials: dict[str, str]) -> CloudAuthResult:
        token = self._form_request(f"{self.AUTH}/token", {
            "client_id": credentials.get("client_id", ""), "grant_type": "refresh_token",
            "refresh_token": refresh_token, "scope": self.SCOPES,
        })
        self.access_token = token["access_token"]
        return self._auth_result(token)

    def upload(self, request: CloudUploadRequest) -> RemoteMetadata:
        name = quote(request.remote_name, safe="")
        if request.remote_id:
            url = f"{self.GRAPH}/me/drive/items/{quote(request.remote_id)}/content"
        elif request.remote_parent_id:
            url = f"{self.GRAPH}/me/drive/items/{quote(request.remote_parent_id)}:/{name}:/content"
        else:
            url = f"{self.GRAPH}/me/drive/root:/{name}:/content"
        if request.local_path.stat().st_size > 4 * 1024 * 1024:
            return self._resumable_upload(url.removesuffix("/content") + "/createUploadSession", request)
        data = request.local_path.read_bytes()
        _status, _headers, body = self._transport("PUT", url, self._authorized("application/octet-stream"), data)
        return self._metadata(json.loads(body.decode()))

    def download(self, remote_id: str, destination: Path) -> Path:
        _status, _headers, body = self._transport(
            "GET", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}/content", self._authorized(), None
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(body)
        return destination

    def delete(self, remote_id: str) -> None:
        self._transport("DELETE", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}", self._authorized(), None)

    def rename(self, remote_id: str, new_name: str) -> RemoteMetadata:
        data, _ = self._json_request("PATCH", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}", {"name": new_name})
        return self._metadata(data)

    def move(self, remote_id: str, parent_id: str) -> RemoteMetadata:
        data, _ = self._json_request(
            "PATCH", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}", {"parentReference": {"id": parent_id}}
        )
        return self._metadata(data)

    def list_changes(self, cursor: str | None = None) -> tuple[list[RemoteMetadata], str | None]:
        url = cursor or f"{self.GRAPH}/me/drive/root/delta"
        changes: list[RemoteMetadata] = []
        final_cursor = cursor
        visited_urls: set[str] = set()
        page = 0
        deadline = time.monotonic() + self.DELTA_DEADLINE_SECONDS
        logger.info(
            "cloud.onedrive.delta.start cursor_present=%s",
            bool(cursor),
        )
        while url:
            if url in visited_urls:
                raise CloudError(
                    "O Microsoft Graph repetiu a mesma página de alterações. "
                    "A sincronização foi interrompida com segurança."
                )
            if page >= self.MAX_DELTA_PAGES or time.monotonic() >= deadline:
                raise CloudError(
                    "A consulta de alterações do OneDrive excedeu o limite seguro."
                )
            visited_urls.add(url)
            page += 1
            logger.info("cloud.onedrive.delta.page page=%s", page)
            data, _ = self._json_request("GET", url)
            changes.extend(self._metadata(item) for item in data.get("value", []))
            next_url = data.get("@odata.nextLink")
            delta_url = data.get("@odata.deltaLink")
            if delta_url:
                final_cursor = delta_url
            url = next_url
        logger.info(
            "cloud.onedrive.delta.done pages=%s changes=%s cursor_updated=%s",
            page, len(changes), final_cursor != cursor,
        )
        return changes, final_cursor

    def get_metadata(self, remote_id: str) -> RemoteMetadata:
        data, _ = self._json_request("GET", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}")
        return self._metadata(data)

    def ensure_folder(self, name: str, parent_id: str | None = None) -> RemoteMetadata:
        clean_name = self._folder_name(name)
        parent_url = (
            f"{self.GRAPH}/me/drive/items/{quote(parent_id)}/children"
            if parent_id
            else f"{self.GRAPH}/me/drive/root/children"
        )
        escaped = clean_name.replace("'", "''")
        query = urlencode({
            "$filter": f"name eq '{escaped}'",
            "$select": "id,name,size,eTag,lastModifiedDateTime,parentReference,folder",
        })
        listing, _ = self._json_request("GET", f"{parent_url}?{query}")
        for item in listing.get("value", []):
            if item.get("folder") is not None and item.get("name") == clean_name:
                return self._metadata(item)
        created, _ = self._json_request(
            "POST",
            parent_url,
            {
                "name": clean_name,
                "folder": {},
                "@microsoft.graph.conflictBehavior": "fail",
            },
        )
        return self._metadata(created)

    def disconnect(self) -> None:
        self.access_token = ""

    @staticmethod
    def _folder_name(name: str) -> str:
        clean = " ".join(name.split()).strip(". ")
        if not clean or len(clean) > 120 or any(character in clean for character in '\\/:*?"<>|'):
            raise ValueError("Nome de pasta incompatível com o OneDrive.")
        return clean

    def _form_request(self, url: str, payload: dict[str, str]) -> dict:
        body = urlencode(payload).encode()
        _status, _headers, response = self._transport(
            "POST", url, {"Content-Type": "application/x-www-form-urlencoded"}, body
        )
        data = json.loads(response.decode())
        if "access_token" not in data:
            raise CloudAuthenticationError("A autenticação do OneDrive não foi concluída.")
        return data

    def _resumable_upload(self, session_url: str, request: CloudUploadRequest) -> RemoteMetadata:
        session, _ = self._json_request(
            "POST", session_url,
            {"item": {"@microsoft.graph.conflictBehavior": "rename", "name": request.remote_name}},
        )
        upload_url = session.get("uploadUrl")
        if not upload_url:
            raise ValueError("O OneDrive não iniciou a sessão de upload.")
        total = request.local_path.stat().st_size
        chunk_size = 10 * 1024 * 1024
        response = b""
        with request.local_path.open("rb") as handle:
            start = 0
            while start < total:
                chunk = handle.read(chunk_size)
                end = start + len(chunk) - 1
                _status, _headers, response = self._transport(
                    "PUT", upload_url,
                    {"Content-Length": str(len(chunk)), "Content-Range": f"bytes {start}-{end}/{total}"},
                    chunk,
                )
                start = end + 1
        return self._metadata(json.loads(response.decode()))

    @staticmethod
    def _auth_result(token: dict, email=None, display_name=None) -> CloudAuthResult:
        return CloudAuthResult(
            access_token=token["access_token"], refresh_token=token.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600))),
            email=email, display_name=display_name,
        )

    @staticmethod
    def _metadata(data: dict) -> RemoteMetadata:
        parent = data.get("parentReference") or {}
        return RemoteMetadata(
            remote_id=str(data.get("id", "")), name=data.get("name", ""),
            size=int(data.get("size", 0) or 0), version=data.get("eTag") or data.get("cTag"),
            modified_at=data.get("lastModifiedDateTime"), parent_id=parent.get("id"),
            deleted="deleted" in data,
        )
