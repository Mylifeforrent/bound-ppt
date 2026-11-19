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
from app.core.idempotency import begin_command, finish_command
from app.services import projects as project_service

router = APIRouter(prefix="/api", tags=["jobs"])


@router.get("/projects/{project_id}/jobs/{job_id}")
async def get_job(
    project_id: UUID,
    job_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    job = await project_service.load_job(session, project.id, job_id)
    started_at = await project_service.job_started_at(session, job.id)
    return envelope(
        project_service.job_dto(job, started_at=started_at),
        ctx=ctx,
        project_version=project.version,
    )


@router.post("/projects/{project_id}/jobs/{job_id}/cancel")
async def cancel_job(
    project_id: UUID,
    job_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:job:{job_id}:cancel",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    job = await project_service.load_job(session, project.id, job_id)
    _changed, sequence = await project_service.cancel_job(session, project, job)
    started_at = await project_service.job_started_at(session, job.id)
    data = {"job": project_service.job_dto(job, started_at=started_at)}
    response = envelope(
        data,
        ctx=ctx,
        project_version=project.version,
        sequence=sequence,
    )
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="job",
        resource_id=job.id,
    )
    await session.commit()
    return response
