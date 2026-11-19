from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError, not_found, validation
from app.core.ids import iso, utcnow
from app.core.security import SESSION_COOKIE, resolve_session
from app.domain.enums import ProjectStatus
from app.models import AppUser, Project


def _request_ids(request: Request) -> tuple[str, str]:
    request_id = request.headers.get("x-request-id") or str(uuid4())
    trace_id = request.headers.get("x-trace-id") or uuid4().hex
    request.state.request_id = request_id
    request.state.trace_id = trace_id
    return request_id, trace_id


async def get_current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> AppUser:
    _request_ids(request)
    token = request.cookies.get(SESSION_COOKIE, "")
    user = await resolve_session(session, token)
    if user is None:
        raise AppError("forbidden", "error.auth.session_required", http_status=401)
    request.state.user_id = str(user.id)
    return user


@dataclass
class CommandContext:
    request_id: str
    trace_id: str
    idempotency_key: str | None
    expected_version: int | None
    user: AppUser

    def require_idempotency(self) -> str:
        if not self.idempotency_key:
            raise validation("error.validation.missing_header", {"header": "Idempotency-Key"})
        return self.idempotency_key

    def require_version(self) -> int:
        if self.expected_version is None:
            raise validation("error.validation.missing_header", {"header": "X-Expected-Version"})
        return self.expected_version


async def command_context(
    request: Request, user: AppUser = Depends(get_current_user)
) -> CommandContext:
    request_id, trace_id = _request_ids(request)
    key = request.headers.get("idempotency-key")
    raw_version = request.headers.get("x-expected-version")
    version = int(raw_version) if raw_version and raw_version.isdigit() else None
    return CommandContext(
        request_id=request_id,
        trace_id=trace_id,
        idempotency_key=key,
        expected_version=version,
        user=user,
    )


async def load_owned_project(
    session: AsyncSession, project_id: UUID, user: AppUser
) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.status == ProjectStatus.DELETED.value:
        raise not_found("error.not_found.project")
    if project.owner_user_id and project.owner_user_id != user.id:
        # Do not reveal existence of another tenant's project.
        raise not_found("error.not_found.project")
    if project.account_id and user.account_id and project.account_id != user.account_id:
        raise not_found("error.not_found.project")
    if project.status == ProjectStatus.DELETING.value:
        raise not_found("error.not_found.project")
    return project


def to_jsonable(value: Any) -> Any:
    if isinstance(value, JSONResponse):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    return jsonable_encoder(value)


def envelope(
    data: Any,
    *,
    ctx: CommandContext | None = None,
    request: Request | None = None,
    project_version: int | None = None,
    sequence: int | None = None,
    idempotent_replay: bool | None = None,
    status_code: int = 200,
) -> JSONResponse:
    request_id = ctx.request_id if ctx else getattr(request.state, "request_id", str(uuid4()))
    trace_id = ctx.trace_id if ctx else getattr(request.state, "trace_id", uuid4().hex)
    meta: dict[str, Any] = {
        "requestId": request_id,
        "traceId": trace_id,
        "serverTime": iso(utcnow()),
    }
    if project_version is not None:
        meta["projectVersion"] = project_version
    if sequence is not None:
        meta["sequence"] = sequence
    if idempotent_replay:
        meta["idempotentReplay"] = True
        return JSONResponse(
            status_code=status_code,
            content={"ok": True, "data": to_jsonable(data), "meta": meta},
            headers={"Idempotent-Replay": "true", "Cache-Control": "no-store"},
        )
    return JSONResponse(
        status_code=status_code,
        content={"ok": True, "data": to_jsonable(data), "meta": meta},
        headers={"Cache-Control": "no-store"},
    )


def replay_response(record, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=record.status_code or 200,
        content=record.response_json or {"ok": True, "data": {}, "meta": {}},
        headers={"Idempotent-Replay": "true", "Cache-Control": "no-store"},
    )
