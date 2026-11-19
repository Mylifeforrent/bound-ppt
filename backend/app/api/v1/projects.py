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
from app.core.errors import validation
from app.core.idempotency import begin_command, finish_command
from app.schemas.dto import (
    CreateProjectRequest,
    PatchProjectRequest,
    ProjectSnapshotDTO,
    RestartRequest,
)
from app.services import projects as project_service
from app.services.jobs import wake_jobs
from app.services.state import build_snapshot

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", status_code=201)
async def create_project(
    payload: CreateProjectRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    payload_dict = payload.model_dump()
    replay, record = await begin_command(
        session,
        scope_key=f"user:{ctx.user.id}:projects:create",
        key=key,
        payload=payload_dict,
    )
    if replay is not None:
        return replay_response(replay, request)

    result = await project_service.create_project(
        session,
        owner_user_id=ctx.user.id,
        account_id=ctx.user.account_id,
        topic=payload.topic,
        name=payload.name,
        mode=payload.mode,
    )
    data = {
        "project": project_service.project_dto(result.project),
        "snapshot": result.snapshot,
    }
    response = envelope(
        data,
        ctx=ctx,
        project_version=result.project.version,
        sequence=result.sequence,
        status_code=201,
    )
    finish_command(
        record,
        status_code=201,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=result.project.id,
    )
    await session.commit()
    return response


@router.get("/{project_id}/snapshot")
async def get_snapshot(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    snapshot: ProjectSnapshotDTO = await build_snapshot(session, project)
    return envelope(
        snapshot,
        ctx=ctx,
        project_version=snapshot.project.version,
        sequence=snapshot.sequence,
    )


@router.patch("/{project_id}")
async def patch_project(
    project_id: UUID,
    payload: PatchProjectRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump(exclude_unset=True)
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:patch",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    if "name" not in payload_dict and "topic" not in payload_dict:
        raise validation("error.validation.invalid_request", {"fields": ["name", "topic"]})
    await project_service.update_project(
        session,
        project,
        name=payload_dict.get("name"),
        topic=payload_dict.get("topic"),
    )
    data = {"project": project_service.project_dto(project)}
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=project.id,
    )
    await session.commit()
    return response


@router.post("/{project_id}/restart", status_code=202)
async def restart_project(
    project_id: UUID,
    payload: RestartRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    if payload.confirm is not True:
        raise validation("error.validation.invalid_request", {"field": "confirm"})
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump()
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:restart",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    result = await project_service.restart_project(session, project)
    data = {
        "project": project_service.project_dto(result.project),
        "snapshot": result.snapshot,
        "cancelledJobIds": result.cancelled_job_ids,
    }
    response = envelope(
        data,
        ctx=ctx,
        project_version=result.project.version,
        sequence=result.sequence,
        status_code=202,
    )
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=result.project.id,
    )
    await session.commit()
    return response


@router.delete("/{project_id}", status_code=202)
async def delete_project(
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
        scope_key=f"project:{project.id}:delete",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    result = await project_service.begin_deletion(session, project)
    data = {
        "projectId": result.project.id,
        "status": "DELETING",
        "jobId": result.job.id,
    }
    response = envelope(
        data,
        ctx=ctx,
        project_version=result.project.version,
        sequence=result.sequence,
        status_code=202,
    )
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=result.project.id,
    )
    await session.commit()
    wake_jobs(result.job)
    return response
