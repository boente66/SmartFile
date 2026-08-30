from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlencode

from app.cloud.cloud_models import (
    CloudAuthResult, CloudStorageQuota, CloudStorageQuotaStatus,
    CloudUploadRequest, RemoteItemType, RemoteMetadata,
)
from app.cloud.cloud_provider import CloudAuthenticationError, CloudError, CloudProvider


class GoogleDriveProvider(CloudProvider):
    API = "https://www.googleapis.com/drive/v3"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3"
    AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN = "https://oauth2.googleapis.com/token"
    # O organizador precisa ler pastas preexistentes escolhidas pelo usuário.
    # drive.file enxerga apenas arquivos criados/abertos pelo aplicativo.
    SCOPES = "openid email profile https://www.googleapis.com/auth/drive"

    def authenticate(self, credentials: dict[str, str]) -> CloudAuthResult:
        action = credentials.get("action", "complete")
        client_id = credentials.get("client_id", "")
        redirect_uri = credentials.get("redirect_uri", "http://localhost")
        if not client_id:
            raise CloudAuthenticationError("Configure SMARTFILE_GOOGLE_DRIVE_CLIENT_ID.")
        if action == "begin":
            verifier = secrets.token_urlsafe(64)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
            query = urlencode({
                "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri,
                "scope": self.SCOPES, "access_type": "offline", "prompt": "consent",
                "code_challenge": challenge, "code_challenge_method": "S256",
            })
            return CloudAuthResult(authorization_url=f"{self.AUTH}?{query}", code_verifier=verifier)
        token = self._token_request({
            "client_id": client_id, "grant_type": "authorization_code", "code": credentials.get("code", ""),
            "redirect_uri": redirect_uri, "code_verifier": credentials.get("code_verifier", ""),
        })
        self.access_token = token["access_token"]
        profile, _ = self._json_request("GET", "https://openidconnect.googleapis.com/v1/userinfo")
        return self._auth_result(token, profile.get("email"), profile.get("name"))

    def refresh_token(self, refresh_token: str, credentials: dict[str, str]) -> CloudAuthResult:
        payload = {
            "client_id": credentials.get("client_id", ""), "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        if credentials.get("client_secret"):
            payload["client_secret"] = credentials["client_secret"]
        token = self._token_request(payload)
        self.access_token = token["access_token"]
        return self._auth_result(token)

    def upload(self, request: CloudUploadRequest) -> RemoteMetadata:
        if request.local_path.stat().st_size > 5 * 1024 * 1024:
            return self._resumable_upload(request)
        boundary = f"smartfile_{secrets.token_hex(12)}"
        metadata = {"name": request.remote_name}
        if request.remote_parent_id:
            metadata["parents"] = [request.remote_parent_id]
        body = (
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n"
        ).encode() + request.local_path.read_bytes() + f"\r\n--{boundary}--".encode()
        if request.remote_id:
            method = "PATCH"; url = f"{self.UPLOAD}/files/{quote(request.remote_id)}?uploadType=multipart&fields=*"
        else:
            method = "POST"; url = f"{self.UPLOAD}/files?uploadType=multipart&fields=*"
        _status, _headers, response = self._transport(
            method, url, self._authorized(f"multipart/related; boundary={boundary}"), body
        )
        return self._metadata(json.loads(response.decode()))

    def _resumable_upload(self, request: CloudUploadRequest) -> RemoteMetadata:
        metadata = {"name": request.remote_name}
        if request.remote_parent_id:
            metadata["parents"] = [request.remote_parent_id]
        if request.remote_id:
            method = "PATCH"; url = f"{self.UPLOAD}/files/{quote(request.remote_id)}?uploadType=resumable&fields=*"
        else:
            method = "POST"; url = f"{self.UPLOAD}/files?uploadType=resumable&fields=*"
        mime = "application/octet-stream"
        headers = self._authorized("application/json; charset=UTF-8")
        headers["X-Upload-Content-Type"] = mime
        headers["X-Upload-Content-Length"] = str(request.local_path.stat().st_size)
        _status, response_headers, _body = self._transport(method, url, headers, json.dumps(metadata).encode())
        location = response_headers.get("Location") or response_headers.get("location")
        if not location:
            raise ValueError("O Google Drive não iniciou a sessão de upload.")
        total = request.local_path.stat().st_size
        chunk_size = 8 * 1024 * 1024
        response = b""
        with request.local_path.open("rb") as handle:
            start = 0
            while start < total:
                chunk = handle.read(chunk_size)
                end = start + len(chunk) - 1
                _status, _headers, response = self._transport(
                    "PUT", location,
                    {
                        "Content-Type": mime,
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {start}-{end}/{total}",
                    },
                    chunk,
                )
                start = end + 1
        return self._metadata(json.loads(response.decode()))

    def download(self, remote_id: str, destination: Path) -> Path:
        _status, _headers, body = self._transport(
            "GET", f"{self.API}/files/{quote(remote_id)}?alt=media", self._authorized(), None
        )
        destination.parent.mkdir(parents=True, exist_ok=True); destination.write_bytes(body); return destination

    def delete(self, remote_id: str) -> None:
        self._transport("DELETE", f"{self.API}/files/{quote(remote_id)}", self._authorized(), None)

    def rename(self, remote_id: str, new_name: str) -> RemoteMetadata:
        data, _ = self._json_request(
            "PATCH", f"{self.API}/files/{quote(remote_id)}?fields=*", {"name": new_name}
        )
        return self._metadata(data)

    def move(self, remote_id: str, parent_id: str) -> RemoteMetadata:
        current = self.get_metadata(remote_id)
        query = urlencode({"addParents": parent_id, "removeParents": current.parent_id or "", "fields": "*"})
        data, _ = self._json_request("PATCH", f"{self.API}/files/{quote(remote_id)}?{query}", {})
        return self._metadata(data)

    def list_changes(self, cursor: str | None = None) -> tuple[list[RemoteMetadata], str | None]:
        if not cursor:
            data, _ = self._json_request("GET", f"{self.API}/changes/startPageToken")
            return [], data.get("startPageToken")
        token = cursor; changes = []
        while token:
            data, _ = self._json_request(
                "GET", f"{self.API}/changes?{urlencode({'pageToken': token, 'fields': 'changes(fileId,removed,file(*)),newStartPageToken,nextPageToken'})}"
            )
            for change in data.get("changes", []):
                file_data = change.get("file") or {"id": change.get("fileId"), "name": "", "trashed": change.get("removed", False)}
                changes.append(self._metadata(file_data))
            token = data.get("nextPageToken")
            cursor = data.get("newStartPageToken", cursor)
        return changes, cursor

    def get_metadata(self, remote_id: str) -> RemoteMetadata:
        data, _ = self._json_request("GET", f"{self.API}/files/{quote(remote_id)}?fields=*")
        return self._metadata(data)

    def get_storage_quota(self) -> CloudStorageQuota:
        data, _ = self._json_request(
            "GET", f"{self.API}/about?fields=storageQuota"
        )
        quota = data.get("storageQuota")
        if not isinstance(quota, dict) or "usage" not in quota:
            raise CloudError("O Google Drive retornou uma resposta de capacidade incompleta.")
        used = self._optional_quota_integer(quota, "usage")
        total = self._optional_quota_integer(quota, "limit")
        available = max(0, total - used) if total is not None and used is not None else None
        return CloudStorageQuota(
            provider="GOOGLE_DRIVE",
            total_bytes=total,
            used_bytes=used,
            available_bytes=available,
            fetched_at=datetime.now(timezone.utc),
            status=CloudStorageQuotaStatus.AVAILABLE,
            provider_state="unlimited" if total is None else "normal",
        )

    def ensure_folder(self, name: str, parent_id: str | None = None) -> RemoteMetadata:
        clean_name = self._folder_name(name)
        escaped = clean_name.replace("\\", "\\\\").replace("'", "\\'")
        clauses = [
            f"name = '{escaped}'",
            "mimeType = 'application/vnd.google-apps.folder'",
            "trashed = false",
        ]
        if parent_id:
            clauses.append(f"'{parent_id}' in parents")
        query = urlencode({
            "q": " and ".join(clauses),
            "fields": "files(id,name,size,version,modifiedTime,parents,trashed)",
            "pageSize": "2",
        })
        listing, _ = self._json_request("GET", f"{self.API}/files?{query}")
        files = listing.get("files", [])
        if files:
            return self._metadata(files[0])
        metadata = {
            "name": clean_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]
        created, _ = self._json_request(
            "POST", f"{self.API}/files?fields=*", metadata
        )
        return self._metadata(created)

    def list_children(self, parent_id: str | None = None) -> list[RemoteMetadata]:
        parent = parent_id or "root"
        token: str | None = None
        result: list[RemoteMetadata] = []
        visited: set[str] = set()
        while True:
            query = {
                "q": f"'{parent}' in parents and trashed = false",
                "fields": (
                    "nextPageToken,files(id,name,size,version,modifiedTime,parents,"
                    "trashed,mimeType,md5Checksum)"
                ),
                "pageSize": "1000",
            }
            if token:
                if token in visited:
                    raise CloudError("O Google Drive repetiu a mesma página remota.")
                visited.add(token)
                query["pageToken"] = token
            data, _ = self._json_request("GET", f"{self.API}/files?{urlencode(query)}")
            result.extend(self._metadata(item) for item in data.get("files", []))
            next_token = data.get("nextPageToken")
            if not next_token:
                break
            token = str(next_token)
        return result

    def list_folders(self, parent_id: str | None = None) -> list[RemoteMetadata]:
        return [
            item for item in self.list_children(parent_id)
            if item.item_type == RemoteItemType.FOLDER
        ]

    def disconnect(self) -> None:
        self.access_token = ""

    @staticmethod
    def _optional_quota_integer(quota: dict, key: str) -> int | None:
        if key not in quota:
            return None
        try:
            value = int(quota[key])
        except (TypeError, ValueError) as exc:
            raise CloudError(
                "O Google Drive retornou uma capacidade inválida."
            ) from exc
        if value < 0:
            raise CloudError("O Google Drive retornou uma capacidade inválida.")
        return value

    @staticmethod
    def _folder_name(name: str) -> str:
        clean = " ".join(name.split()).strip()
        if not clean or len(clean) > 120 or "/" in clean or "\x00" in clean:
            raise ValueError("Nome de pasta incompatível com o Google Drive.")
        return clean

    def _token_request(self, payload: dict[str, str]) -> dict:
        _status, _headers, response = self._transport(
            "POST", self.TOKEN, {"Content-Type": "application/x-www-form-urlencoded"}, urlencode(payload).encode()
        )
        data = json.loads(response.decode())
        if "access_token" not in data:
            raise CloudAuthenticationError("A autenticação do Google Drive não foi concluída.")
        return data

    @staticmethod
    def _auth_result(token: dict, email=None, display_name=None) -> CloudAuthResult:
        return CloudAuthResult(
            access_token=token["access_token"], refresh_token=token.get("refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=int(token.get("expires_in", 3600))),
            email=email, display_name=display_name,
        )

    @staticmethod
    def _metadata(data: dict) -> RemoteMetadata:
        parents = data.get("parents") or []
        return RemoteMetadata(
            remote_id=str(data.get("id", "")), name=data.get("name", ""),
            size=int(data.get("size", 0) or 0), version=data.get("version") or data.get("md5Checksum"),
            modified_at=data.get("modifiedTime"), parent_id=parents[0] if parents else None,
            deleted=bool(data.get("trashed", False)),
            item_type=(
                RemoteItemType.FOLDER
                if data.get("mimeType") == "application/vnd.google-apps.folder"
                else RemoteItemType.FILE if data.get("mimeType") else RemoteItemType.UNKNOWN
            ),
            mime_type=data.get("mimeType"),
            provider_hash=data.get("md5Checksum"),
        )
