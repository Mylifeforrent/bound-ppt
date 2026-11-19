from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CommandContext, command_context, envelope, get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError, validation
from app.core.ids import iso, new_id, utcnow
from app.models import AppUser, PolicyRecord
from app.schemas.dto import (
    ClientConfigDTO,
    ConsentRequest,
    NoticeDTO,
    NoticesDTO,
    SupportedFileType,
)
from app.storage import ALLOWED_UPLOAD_TYPES, LocalStorage, storage

router = APIRouter(tags=["system"])

NOTICE_VERSION = "2026-11-01"
NOTICE_TITLE = "How we handle your materials"
NOTICE_BODY = (
    "Your materials are used only to produce your deck. Customer content is not used to train models. "
    "You can remove materials and delete the project at any time; derived artifacts follow the project "
    "retention policy. Do not upload data you are not authorized to process."
)


async def _accepted_at(session: AsyncSession, user: AppUser) -> datetime | None:
    return await session.scalar(
        select(PolicyRecord.accepted_at).where(
            PolicyRecord.scope_type == "user",
            PolicyRecord.scope_id == user.id,
            PolicyRecord.type == "DATA_NOTICE",
            PolicyRecord.version == NOTICE_VERSION,
            PolicyRecord.accepted_at.is_not(None),
        )
    )


async def has_consent(session: AsyncSession, user: AppUser) -> bool:
    return (await _accepted_at(session, user)) is not None


@router.get("/api/config")
async def client_config(user: AppUser = Depends(get_current_user), request: Request = None):
    settings = get_settings()
    types = [
        SupportedFileType(
            extension=ext,
            mime_type=mime,
            max_bytes=settings.upload_max_bytes,
            max_pages=200 if ext == ".pdf" else None,
        )
        for ext, mime in ALLOWED_UPLOAD_TYPES.items()
    ]
    cfg = ClientConfigDTO(
        material_limit=settings.material_max_count,
        page_limit=settings.page_max_count,
        upload_max_bytes=settings.upload_max_bytes,
        supported_file_types=types,
        search_cap_per_project=settings.search_cap_per_project,
        export_formats=["PPTX", "HTML", "PDF"],
        deck_canvas={"width": 1280, "height": 720},
        question_catalog_version=settings.question_catalog_version,
        style_catalog_version=settings.style_catalog_version,
    )
    return envelope({"config": cfg}, request=request)


@router.get("/api/policy/notices")
async def notices(
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    accepted = await _accepted_at(session, user)
    dto = NoticesDTO(
        notices=[
            NoticeDTO(
                type="DATA_NOTICE",
                version=NOTICE_VERSION,
                title=NOTICE_TITLE,
                body=NOTICE_BODY,
                requires_consent=True,
                accepted_at=iso(accepted),
            )
        ]
    )
    return envelope(dto, request=request)


@router.post("/api/policy/consent")
async def consent(
    payload: ConsentRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    ctx.require_idempotency()
    if payload.version != NOTICE_VERSION:
        raise validation("error.validation.notice_version_unknown")
    existing = await _accepted_at(session, ctx.user)
    if existing is None:
        session.add(
            PolicyRecord(
                id=new_id(),
                scope_type="user",
                scope_id=ctx.user.id,
                project_id=None,
                type="DATA_NOTICE",
                version=NOTICE_VERSION,
                accepted_by_user_id=ctx.user.id,
                accepted_at=utcnow(),
            )
        )
        await session.commit()
        existing = await _accepted_at(session, ctx.user)
    return envelope({"acceptedAt": iso(existing), "version": NOTICE_VERSION}, ctx=ctx)


@router.get("/api/health")
async def health():
    return {"status": "ok"}


@router.get("/api/health/ready")
async def ready(response: Response, session: AsyncSession = Depends(get_session)):
    checks = {"database": "ok", "migrations": "ok", "objectStore": "ok", "runner": "ok"}
    try:
        await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        checks["database"] = "fail"
    if checks["database"] == "ok":
        try:
            settings = get_settings()
            if isinstance(storage, LocalStorage):
                storage.root.mkdir(parents=True, exist_ok=True)
            elif not settings.s3_bucket:
                checks["objectStore"] = "fail"
        except Exception:  # noqa: BLE001
            checks["objectStore"] = "fail"
    else:
        checks["objectStore"] = "skip"
    from app.worker.runner import runner

    if not runner._started:
        checks["runner"] = "fail"
    ok = all(v in {"ok", "skip"} for v in checks.values())
    response.status_code = 200 if ok else 503
    return {"status": "ready" if ok else "degraded", "checks": checks}


@router.put("/api/uploads/{token}")
async def upload_object(token: str, request: Request):
    if not isinstance(storage, LocalStorage):
        raise AppError("not_found", "error.not_found.asset")
    try:
        key = storage.verify_put_token(token)
    except ValueError as exc:
        raise validation("error.validation.upload_missing") from exc
    body = await request.body()
    if len(body) > get_settings().upload_max_bytes:
        raise validation("error.validation.file_too_large")
    content_type = request.headers.get("content-type", "application/octet-stream")
    storage.put_bytes(key, body, content_type)
    return {"ok": True, "sizeBytes": len(body)}


@router.get("/api/downloads/{token}")
async def download_object(token: str):
    if not isinstance(storage, LocalStorage):
        raise AppError("not_found", "error.not_found.asset")
    try:
        key = storage.verify_get_token(token)
    except ValueError as exc:
        raise AppError("not_found", "error.not_found.asset") from exc
    path = storage._path(key)  # local adapter path
    if not path.is_file():
        raise AppError("not_found", "error.not_found.asset")
    import mimetypes

    media, _ = mimetypes.guess_type(str(path))
    return FileResponse(path, media_type=media or "application/octet-stream", filename=Path(key).name)
