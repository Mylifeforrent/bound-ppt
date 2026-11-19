from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    load_owned_project,
    replay_response,
)
from app.core.db import get_session
from app.core.errors import gate, not_found, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.domain.enums import ArtifactKind, JobType
from app.models import Page, Project
from app.schemas.dto import (
    ArtifactDTO,
    PageActionRequest,
    PageHistoryDTO,
    PageJobResultDTO,
    PageListDTO,
    UndoResultDTO,
)
from app.services import artifacts, state
from app.services.events import events
from app.services.jobs import enqueue_job, find_active, wake_jobs
from app.services.stages import emit_stage_state

router = APIRouter(tags=["pages"])


def _normalize_kind(kind: str) -> str:
    value = (kind or "").upper()
    if value not in {ArtifactKind.PLAN.value, ArtifactKind.DESIGN.value}:
        raise validation("error.validation.invalid_request", {"field": "kind"})
    return value


async def _require_outline_page(session: AsyncSession, project: Project, page_id: UUID):
    bundle = await state.load_outline(session, project)
    page = bundle.by_page.get(page_id)
    if bundle.version is None or page is None:
        raise not_found("error.not_found.outline")
    return bundle, page


@router.get("/api/projects/{project_id}/pages")
async def list_pages(
    project_id: UUID,
    kind: str | None = Query(default=None),
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    if kind is not None:
        _normalize_kind(kind)
    page_list: PageListDTO = await state.build_page_list(session, project)
    return envelope(page_list, ctx=ctx, project_version=project.version)


@router.get("/api/projects/{project_id}/pages/{page_id}/artifacts/{kind}")
async def get_artifact(
    project_id: UUID,
    page_id: UUID,
    kind: str,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    project = await load_owned_project(session, project_id, ctx.user)
    normalized = _normalize_kind(kind)
    dto: ArtifactDTO = await artifacts.build_artifact_dto(session, project, page_id, normalized)
    etag = f'"{dto.content_digest}"'
    if request is not None and request.headers.get("if-none-match") in {etag, dto.content_digest}:
        return Response(status_code=304, headers={"ETag": etag, "Cache-Control": "no-store"})
    response = envelope(dto, ctx=ctx, project_version=project.version)
    response.headers["ETag"] = etag
    return response


@router.get("/api/projects/{project_id}/pages/{page_id}/history")
async def get_history(
    project_id: UUID,
    page_id: UUID,
    kind: str = Query(default="design"),
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    normalized = _normalize_kind(kind)
    await _require_outline_page(session, project, page_id)
    pointer = await artifacts.pointer_for(session, project, page_id, normalized)
    dto: PageHistoryDTO = await artifacts.history_dto(
        session,
        project,
        page_id,
        normalized,
        pointer.artifact_version_id if pointer is not None else None,
    )
    return envelope(dto, ctx=ctx, project_version=project.version)


@router.post("/api/projects/{project_id}/pages/{page_id}/retry", status_code=202)
async def retry_page(
    project_id: UUID,
    page_id: UUID,
    payload: PageActionRequest,
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
        scope_key=f"project:{project.id}:page:{page_id}:retry:{payload.kind}",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await _require_outline_page(session, project, page_id)
    active = await find_active(session, f"page:{page_id}")
    if active is not None:
        raise gate("error.gate.page_write_in_progress", {"pageId": str(page_id)})

    normalized = ArtifactKind.PLAN.value if payload.kind == "plan" else ArtifactKind.DESIGN.value
    if normalized == ArtifactKind.DESIGN.value:
        plan_pointer = await artifacts.pointer_for(session, project, page_id, ArtifactKind.PLAN.value)
        if plan_pointer is None:
            raise gate("error.gate.plan_incomplete", {"pageId": str(page_id)})
        selection, definition = await state.load_style_selection(session, project)
        if selection is None or definition is None:
            raise gate("error.gate.style_not_selected")
        if not selection.confirmed_at:
            raise gate("error.gate.style_unconfirmed")

    job_type = JobType.PLAN_PAGE.value if normalized == ArtifactKind.PLAN.value else JobType.DESIGN_PAGE.value
    job = await enqueue_job(
        session,
        project,
        job_type,
        operation_key=f"retry:{normalized.lower()}:{page_id}:{project.version}",
        active_operation_key=f"page:{page_id}",
        payload={"pageId": str(page_id), "kind": normalized, "reason": "RETRY"},
    )
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project)

    data = PageJobResultDTO(job_id=job.id, page_id=page_id)
    response = envelope(data, ctx=ctx, project_version=project.version, status_code=202)
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="job",
        resource_id=job.id,
    )
    await session.commit()
    wake_jobs(job)
    return response


@router.post("/api/projects/{project_id}/pages/{page_id}/undo")
async def undo_page(
    project_id: UUID,
    page_id: UUID,
    payload: PageActionRequest,
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
        scope_key=f"project:{project.id}:page:{page_id}:undo:{payload.kind}",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await _require_outline_page(session, project, page_id)
    active = await find_active(session, f"page:{page_id}")
    if active is not None:
        raise gate("error.gate.page_write_in_progress", {"pageId": str(page_id)})
    normalized = ArtifactKind.PLAN.value if payload.kind == "plan" else ArtifactKind.DESIGN.value
    page = await session.get(Page, page_id)
    if page is None or page.retired_at is not None:
        raise not_found("error.not_found.artifact")

    design_pointer = (
        await artifacts.pointer_for(session, project, page_id, ArtifactKind.DESIGN.value)
        if normalized == ArtifactKind.PLAN.value
        else None
    )
    restored, _pointer = await artifacts.undo(session, project, page, normalized)
    await session.flush()

    history = await artifacts.history_dto(session, project, page_id, normalized, restored.id)
    artifact_dto = await artifacts.build_artifact_dto(session, project, page_id, normalized)

    await events.append(
        session,
        project.id,
        "historyPopped",
        {
            "pageId": str(page_id),
            "kind": normalized,
            "restoredArtifactVersionId": str(restored.id),
            "version": restored.version,
            "historyDepth": history.depth,
            "projectVersion": project.version,
        },
    )
    stale = None
    if normalized == ArtifactKind.PLAN.value and design_pointer is not None:
        stale = state.make_stale_summary(
            project,
            "UNDO",
            plan_pages=[],
            design_pages=[page_id],
            changed_pages=1,
        )
        await events.append(
            session,
            project.id,
            "staleChanged",
            {
                "fromStage": "PLAN",
                "cause": "UNDO",
                "affectedPageIds": [str(page_id)],
                "affectedPages": 1,
                "rerunPages": 1,
                "cascadeRatio": 1.0,
                "projectVersion": project.version,
            },
        )
    await emit_stage_state(session, project)

    data = UndoResultDTO(artifact=artifact_dto, history=history, stale=stale)
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="artifact",
        resource_id=restored.id,
    )
    await session.commit()
    return response


@router.get("/api/projects/{project_id}/assets/{asset_id}")
async def get_asset(
    project_id: UUID,
    asset_id: str,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    # M1 stores no generated asset blobs; an unknown or unreferenced id is a 404.
    await load_owned_project(session, project_id, ctx.user)
    raise not_found("error.not_found.asset")
