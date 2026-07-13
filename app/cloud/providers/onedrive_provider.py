from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from app.cloud.cloud_models import CloudAuthResult, CloudUploadRequest, RemoteMetadata
from app.cloud.cloud_provider import CloudAuthenticationError, CloudProvider


class OneDriveProvider(CloudProvider):
    GRAPH = "https://graph.microsoft.com/v1.0"
    AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0"
    SCOPES = "offline_access User.Read Files.ReadWrite"

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
        changes = []
        final_cursor = cursor
        while url:
            data, _ = self._json_request("GET", url)
            changes.extend(self._metadata(item) for item in data.get("value", []))
            url = data.get("@odata.nextLink")
            final_cursor = data.get("@odata.deltaLink", final_cursor)
        return changes, final_cursor

    def get_metadata(self, remote_id: str) -> RemoteMetadata:
        data, _ = self._json_request("GET", f"{self.GRAPH}/me/drive/items/{quote(remote_id)}")
        return self._metadata(data)

    def disconnect(self) -> None:
        self.access_token = ""

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
