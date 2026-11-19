from __future__ import annotations

import inspect
import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    load_owned_project,
    replay_response,
)
from app.core.db import get_session
from app.core.errors import gate
from app.core.idempotency import begin_command, finish_command
from app.schemas.dto import ExportCreateRequest
from app.services import export as export_service
from app.services.jobs import wake_jobs
from app.storage import storage

router = APIRouter(tags=["exports"])


async def _resolve(value):
    return await value if inspect.isawaitable(value) else value


@router.post("/api/projects/{project_id}/exports", status_code=202)
async def create_export(
    project_id: UUID,
    payload: ExportCreateRequest,
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
        scope_key=f"project:{project.id}:exports:create",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    result = await export_service.start_export(session, project, payload.format)
    data = {"export": export_service.export_dto(result.export, None)}
    response = envelope(data, ctx=ctx, project_version=project.version, status_code=202)
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="export",
        resource_id=result.export.id,
    )
    await session.commit()
    wake_jobs(result.job)
    return response


@router.get("/api/projects/{project_id}/exports/{export_id}")
async def get_export(
    project_id: UUID,
    export_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    export = await export_service.load_export(session, project, export_id)
    artifact = await export_service.load_artifact(session, export.id)
    return envelope(
        export_service.export_dto(export, artifact),
        ctx=ctx,
        project_version=project.version,
    )


@router.get("/api/exports/{export_id}/download")
async def download_export(
    export_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    from app.models import ExportJob

    export = await session.get(ExportJob, export_id)
    if export is None:
        from app.core.errors import not_found

        raise not_found("error.not_found.export")
    await load_owned_project(session, export.project_id, ctx.user)
    artifact = await export_service.load_artifact(session, export.id)
    if export.state != "SUCCEEDED" or artifact is None:
        raise gate("error.gate.export_not_ready", {"exportId": str(export.id), "state": export.state})
    url = await _resolve(storage.presign_get(artifact.object_key))
    return RedirectResponse(
        url=str(url),
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )
