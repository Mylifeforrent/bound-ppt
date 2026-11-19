from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.core.config import Settings, get_settings

ALLOWED_UPLOAD_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".csv": "text/csv",
}


@dataclass
class StoredObject:
    key: str
    size: int
    content_type: str


class LocalStorage:
    """Filesystem-backed object storage for local development.

    The metadata contract (object keys, presigned-style handshakes) is identical to S3.
    """

    def __init__(self, root: Path, secret: str) -> None:
        self.root = root
        self.secret = secret
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        clean = key.lstrip("/")
        if ".." in Path(clean).parts:
            raise ValueError("invalid object key")
        return self.root / clean

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(key=key, size=len(data), content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def size(self, key: str) -> int:
        path = self._path(key)
        return path.stat().st_size if path.is_file() else 0

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_file():
            path.unlink()

    def presign_put(self, key: str, mime_type: str, expires_seconds: int = 900) -> dict[str, Any]:
        token = self._sign("put", key, expires_seconds)
        return {
            "url": f"/api/uploads/{token}",
            "method": "PUT",
            "headers": {"Content-Type": mime_type},
            "expiresAt": _iso(datetime.now(UTC) + timedelta(seconds=expires_seconds)),
            "objectKey": key,
        }

    def verify_put_token(self, token: str) -> str:
        return self._verify("put", token)

    def presign_get(self, key: str, expires_seconds: int = 900) -> str:
        token = self._sign("get", key, expires_seconds)
        return f"/api/downloads/{token}"

    def verify_get_token(self, token: str) -> str:
        return self._verify("get", token)

    def _sign(self, purpose: str, key: str, expires_seconds: int) -> str:
        expires = int(datetime.now(UTC).timestamp()) + expires_seconds
        payload = f"{purpose}:{key}:{expires}"
        mac = hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        raw = json.dumps({"p": purpose, "k": key, "e": expires, "m": mac}, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def _verify(self, purpose: str, token: str) -> str:
        padded = token + "=" * (-len(token) % 4)
        try:
            data = json.loads(base64.urlsafe_b64decode(padded))
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid token") from exc
        if data.get("p") != purpose or int(data.get("e", 0)) < int(datetime.now(UTC).timestamp()):
            raise ValueError("expired token")
        payload = f"{purpose}:{data['k']}:{data['e']}"
        expected = hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
        if not hmac.compare_digest(expected, data.get("m", "")):
            raise ValueError("bad signature")
        return str(data["k"])


class S3Storage:
    """S3-compatible storage adapter. boto3 is synchronous and runs in a thread."""

    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            region_name=settings.s3_region or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None,
        )

    async def _to_thread(self, fn, *args, **kwargs):
        import asyncio

        return await asyncio.to_thread(fn, *args, **kwargs)

    async def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> StoredObject:
        await self._to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        return StoredObject(key=key, size=len(data), content_type=content_type)

    async def get_bytes(self, key: str) -> bytes:
        response = await self._to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        return response["Body"].read()

    async def exists(self, key: str) -> bool:
        try:
            await self._to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False

    async def size(self, key: str) -> int:
        try:
            response = await self._to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
            return int(response.get("ContentLength", 0))
        except Exception:  # noqa: BLE001
            return 0

    async def presign_put(self, key: str, mime_type: str, expires_seconds: int = 900) -> dict[str, Any]:
        url = await self._to_thread(
            self.client.generate_presigned_url,
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": mime_type},
            ExpiresIn=expires_seconds,
        )
        return {
            "url": url,
            "method": "PUT",
            "headers": {"Content-Type": mime_type},
            "expiresAt": _iso(datetime.now(UTC) + timedelta(seconds=expires_seconds)),
            "objectKey": key,
        }

    async def presign_get(self, key: str, expires_seconds: int = 900) -> str:
        return await self._to_thread(
            self.client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def file_content_type(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix in ALLOWED_UPLOAD_TYPES:
        return ALLOWED_UPLOAD_TYPES[suffix]
    guessed, _ = mimetypes.guess_type(file_name)
    return guessed or "application/octet-stream"


def quote_object_key(key: str) -> str:
    return quote(key, safe="")


def make_storage() -> Any:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.storage_root, settings.session_secret)


storage = make_storage()
