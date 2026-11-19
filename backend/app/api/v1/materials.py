from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    load_owned_project,
    replay_response,
)
from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.core.ids import new_id, utcnow
from app.domain.enums import MaterialKind, MaterialStatus
from app.ingest import parsers
from app.models import Material
from app.schemas.dto import (
    AddPasteRequest,
    AddUrlRequest,
    UploadInstruction,
    UploadUrlDTO,
    UploadUrlRequest,
)
from app.services import materials as material_service
from app.services.events import events
from app.services.jobs import wake_jobs
from app.services.stages import emit_stale_changed
from app.services.state import load_outline, make_stale_summary
from app.storage import ALLOWED_UPLOAD_TYPES, storage

router = APIRouter(prefix="/api/projects/{project_id}/materials", tags=["materials"])


def _status_event(material: Material, project_version: int) -> dict:
    return material_service.material_status_payload(material, project_version)


async def _commit_response(
    session: AsyncSession,
    ctx: CommandContext,
    record,
    *,
    data: dict,
    project_version: int,
    status_code: int,
    resource_id: UUID,
):
    response = envelope(data, ctx=ctx, project_version=project_version, status_code=status_code)
    finish_command(
        record,
        status_code=status_code,
        response=json.loads(response.body),
        resource_type="material",
        resource_id=resource_id,
    )
    await session.commit()
    return response


@router.get("")
async def list_materials(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    dto = await material_service.build_material_list(session, project)
    return envelope(dto, ctx=ctx, project_version=project.version)


@router.post("/paste", status_code=202)
async def add_paste(
    project_id: UUID,
    payload: AddPasteRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump()
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:materials:paste",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    text = material_service.validate_paste(payload.text)
    await material_service.assert_add_allowed(session, project, ctx.user)

    material_id = new_id()
    content_ref = parsers.material_content_key(str(project.id), str(material_id))
    encoded = text.encode("utf-8")
    # Content before metadata: an orphan object is recoverable, a row without content is not.
    await material_service.maybe_await(storage.put_bytes(content_ref, encoded, "text/plain"))

    material = Material(
        id=material_id,
        project_id=project.id,
        kind=MaterialKind.PASTE.value,
        status=MaterialStatus.PENDING.value,
        display_name=(payload.display_name or "").strip() or "Pasted text",
        mime_type="text/plain",
        size_bytes=len(encoded),
        content_ref=content_ref,
        version=1,
    )
    session.add(material)
    await session.flush()
    job = await material_service.enqueue_ingest(session, project, material)
    bump_project(project)
    await session.flush()
    await events.append(session, project.id, "materialStatusChanged", _status_event(material, project.version))

    response = await _commit_response(
        session,
        ctx,
        record,
        data={"material": material_service.material_dto(material, job), "jobId": job.id},
        project_version=project.version,
        status_code=202,
        resource_id=material.id,
    )
    wake_jobs(job)
    return response


@router.post("/url", status_code=202)
async def add_url(
    project_id: UUID,
    payload: AddUrlRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump()
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:materials:url",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    normalized_url, domain = material_service.normalize_material_url(payload.url)
    await material_service.assert_add_allowed(session, project, ctx.user)

    material = Material(
        id=new_id(),
        project_id=project.id,
        kind=MaterialKind.URL.value,
        status=MaterialStatus.PENDING.value,
        display_name=(payload.display_name or "").strip() or domain or "Web page",
        mime_type=None,
        size_bytes=0,
        source_url=normalized_url,
        domain=domain,
        version=1,
    )
    session.add(material)
    await session.flush()
    job = await material_service.enqueue_ingest(session, project, material)
    bump_project(project)
    await session.flush()
    await events.append(session, project.id, "materialStatusChanged", _status_event(material, project.version))

    response = await _commit_response(
        session,
        ctx,
        record,
        data={"material": material_service.material_dto(material, job), "jobId": job.id},
        project_version=project.version,
        status_code=202,
        resource_id=material.id,
    )
    wake_jobs(job)
    return response


@router.post("/upload-url")
async def create_upload_url(
    project_id: UUID,
    payload: UploadUrlRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump()
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:materials:upload-url",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    mime_type, _ = material_service.validate_upload_request(
        payload.file_name, payload.mime_type, payload.size_bytes
    )
    await material_service.assert_add_allowed(session, project, ctx.user)

    material_id = new_id()
    raw_ref = parsers.material_raw_key(str(project.id), str(material_id), payload.file_name)
    material = Material(
        id=material_id,
        project_id=project.id,
        kind=MaterialKind.FILE.value,
        status=MaterialStatus.PENDING.value,
        display_name=payload.file_name.strip(),
        mime_type=mime_type,
        size_bytes=payload.size_bytes,
        raw_ref=raw_ref,
        version=1,
    )
    session.add(material)
    await session.flush()

    instruction = await material_service.maybe_await(storage.presign_put(raw_ref, mime_type))
    bump_project(project)
    await session.flush()
    await events.append(session, project.id, "materialStatusChanged", _status_event(material, project.version))

    dto = UploadUrlDTO(
        material_id=material.id,
        upload=UploadInstruction(
            url=str(instruction["url"]),
            method=str(instruction.get("method") or "PUT"),
            headers={str(k): str(v) for k, v in (instruction.get("headers") or {}).items()},
            expires_at=instruction.get("expiresAt") or "",
        ),
    )
    return await _commit_response(
        session,
        ctx,
        record,
        data=dto.model_dump(by_alias=True),
        project_version=project.version,
        status_code=200,
        resource_id=material.id,
    )


@router.post("/{material_id}/finalize", status_code=202)
async def finalize_upload(
    project_id: UUID,
    material_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:material:{material_id}:finalize",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_finalize_allowed(session, project)
    material = await material_service.get_active_material(session, project, material_id)
    if material.kind != MaterialKind.FILE.value or not material.raw_ref:
        raise validation("error.validation.upload_missing")

    exists = await material_service.maybe_await(storage.exists(material.raw_ref))
    if not exists:
        raise validation("error.validation.upload_missing")
    size = int(await material_service.maybe_await(storage.size(material.raw_ref)) or 0)
    if size <= 0:
        raise validation("error.validation.upload_missing")
    settings = get_settings()
    if size > settings.upload_max_bytes:
        raise validation("error.validation.file_too_large")

    suffix = parsers.normalize_filename_extension(material.raw_ref)
    if suffix not in ALLOWED_UPLOAD_TYPES:
        raise validation("error.validation.unsupported_type")
    expected_mime = ALLOWED_UPLOAD_TYPES[suffix]
    if material.mime_type and material.mime_type != expected_mime:
        raise AppError("parse_failure", "error.parse.type_mismatch")

    material.mime_type = expected_mime
    material.size_bytes = size
    material.status = MaterialStatus.PENDING.value
    material.error_code = None
    material.error_message_key = None
    await session.flush()
    job = await material_service.enqueue_ingest(session, project, material)
    bump_project(project)
    await session.flush()
    await events.append(session, project.id, "materialStatusChanged", _status_event(material, project.version))

    response = await _commit_response(
        session,
        ctx,
        record,
        data={"material": material_service.material_dto(material, job), "jobId": job.id},
        project_version=project.version,
        status_code=202,
        resource_id=material.id,
    )
    wake_jobs(job)
    return response


@router.delete("/{material_id}")
async def remove_material(
    project_id: UUID,
    material_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:material:{material_id}:delete",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_project_active(project)
    await material_service.assert_material_stage_mutable(project)
    material = await material_service.get_active_material(session, project, material_id)

    await material_service.cancel_jobs_for_material(session, project, material.id)
    material.status = MaterialStatus.REMOVED.value
    material.removed_at = utcnow()
    await session.flush()
    await material_service.delete_material_objects(material)

    bump_project(project)
    await session.flush()
    await events.append(
        session, project.id, "materialStatusChanged", _status_event(material, project.version)
    )

    stale = None
    bundle = await load_outline(session, project)
    if bundle.version is not None and bundle.pages:
        page_ids = [page.page_id for page in bundle.pages]
        stale = make_stale_summary(
            project, "MATERIAL_REMOVED", plan_pages=page_ids, design_pages=list(page_ids)
        )
        await emit_stale_changed(
            session,
            project,
            from_stage=project.stage,
            cause="MATERIAL_REMOVED",
            affected_plan=page_ids,
            affected_design=list(page_ids),
            changed_pages=len(page_ids),
        )

    return await _commit_response(
        session,
        ctx,
        record,
        data={"materialId": str(material.id), "removed": True, "stale": stale},
        project_version=project.version,
        status_code=200,
        resource_id=material.id,
    )
