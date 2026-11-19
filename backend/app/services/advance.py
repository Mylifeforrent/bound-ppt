from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.errors import conflict, gate


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def issue_advance_token(*, project_id: UUID, from_stage: str, stage_version: int) -> tuple[str, int]:
    settings = get_settings()
    payload = {
        "projectId": str(project_id),
        "fromStage": from_stage,
        "stageVersion": stage_version,
        "issuedAt": int(time.time()),
        "nonce": _b64(hashlib.sha256(f"{project_id}:{time.time_ns()}".encode()).digest()[:12]),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(settings.session_secret.encode(), raw, hashlib.sha256).digest()
    token = f"{_b64(raw)}.{_b64(sig)}"
    return token, int(time.time()) + 30


def validate_advance_token(token: str, *, project_id: UUID, from_stage: str, stage_version: int) -> None:
    settings = get_settings()
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _unb64(raw_b64)
        sig = _unb64(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise gate("error.gate.auto_advance_ineligible") from exc
    expected = hmac.new(settings.session_secret.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        raise gate("error.gate.auto_advance_ineligible")
    payload: dict[str, Any] = json.loads(raw)
    if int(payload.get("issuedAt", 0)) + 30 < int(time.time()):
        raise gate("error.gate.token_expired")
    if payload.get("projectId") != str(project_id) or payload.get("fromStage") != from_stage:
        raise conflict("error.conflict.stage_changed")
    if int(payload.get("stageVersion", -1)) != stage_version:
        raise gate("error.gate.auto_advance_ineligible")
