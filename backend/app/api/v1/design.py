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
from app.core.db import get_session
from app.core.errors import gate, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.domain.enums import PageStatus, Stage
from app.models import Project
from app.schemas.dto import GeneratePagesResultDTO, PageJobResultDTO, TweakRequest
from app.services import generation, state
from app.services.jobs import wake_jobs
from app.services.stages import emit_stage_state

router = APIRouter(tags=["design"])

MAX_INSTRUCTION_CHARS = 2000


def _instruction(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        raise validation("error.validation.empty_instruction")
    if len(text) > MAX_INSTRUCTION_CHARS:
        raise validation(
            "error.validation.invalid_request",
            {"field": "instruction", "maxLength": MAX_INSTRUCTION_CHARS},
        )
    return text


async def _require_style_ready(session: AsyncSession, project: Project):
    selection, definition = await state.load_style_selection(session, project)
    if selection is None or definition is None:
        raise gate("error.gate.style_not_selected")
    if not selection.confirmed_at:
        raise gate("error.gate.style_unconfirmed")
    return selection, definition


async def _require_plan_complete(session: AsyncSession, project: Project) -> None:
    page_list = await state.build_page_list(session, project)
    if not page_list.pages or any(page.plan.status != PageStatus.DONE.value for page in page_list.pages):
        raise gate("error.gate.plan_incomplete")


async def _enqueue_single(
    session: AsyncSession,
    project: Project,
    page_id: UUID,
    *,
    reason: str,
    instruction: str | None,
):
    job = await generation.enqueue_page_job(
        session,
        project,
        page_id,
        "DESIGN",
        reason=reason,
        instruction=instruction,
    )
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project)
    return job


@router.post("/api/projects/{project_id}/design/generate", status_code=202)
async def generate_design(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:design:generate",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await _require_style_ready(session, project)
    await _require_plan_complete(session, project)
    result = await generation.fan_out_pages(session, project, "DESIGN", reason="REGENERATE")
    project.stage = Stage.DESIGN.value
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project, previous_status="AVAILABLE")

    data = GeneratePagesResultDTO(
        jobs=result.jobs,
        skipped_page_ids=result.skipped_page_ids,
        counts={
            "required": result.required,
            "scheduled": len(result.jobs),
            "reused": len(result.skipped_page_ids),
        },
    )
    response = envelope(data, ctx=ctx, project_version=project.version, status_code=202)
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=project.id,
    )
    await session.commit()
    wake_jobs(*result.job_rows)
    return response


@router.post("/api/projects/{project_id}/pages/{page_id}/design/regenerate", status_code=202)
async def regenerate_design(
    project_id: UUID,
    page_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:page:{page_id}:design:regenerate",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await _require_style_ready(session, project)
    job = await _enqueue_single(session, project, page_id, reason="REGENERATE", instruction=None)
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


@router.post("/api/projects/{project_id}/pages/{page_id}/design/tweak", status_code=202)
async def tweak_design(
    project_id: UUID,
    page_id: UUID,
    payload: TweakRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    instruction = _instruction(payload.instruction)
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:page:{page_id}:design:tweak",
        key=key,
        payload={"instruction": instruction},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await _require_style_ready(session, project)
    job = await _enqueue_single(session, project, page_id, reason="TWEAK", instruction=instruction)
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
