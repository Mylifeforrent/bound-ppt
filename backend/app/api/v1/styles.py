from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    get_current_user,
    load_owned_project,
    replay_response,
)
from app.core.db import get_session
from app.core.errors import gate, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.core.ids import new_id, utcnow
from app.domain.enums import PageStatus, Stage
from app.models import AppUser, ArtifactPointer, Project, StyleSelection
from app.schemas.dto import StyleSelectRequest
from app.services import state
from app.services import styles as style_service
from app.services.events import events
from app.services.stages import emit_stage_state

router = APIRouter(tags=["style"])


async def _plan_complete(session: AsyncSession, project: Project) -> bool:
    page_list = await state.build_page_list(session, project)
    if not page_list.pages:
        return False
    return all(page.plan.status == PageStatus.DONE.value for page in page_list.pages)


async def _design_page_ids(session: AsyncSession, project: Project) -> list[UUID]:
    return list(
        (
            await session.scalars(
                select(ArtifactPointer.page_id).where(
                    ArtifactPointer.project_id == project.id,
                    ArtifactPointer.kind == "DESIGN",
                )
            )
        ).all()
    )


@router.get("/api/styles")
async def list_styles(
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    created = await style_service.seed_styles(session)
    if created:
        await session.commit()
    rows = await style_service.list_styles(session)
    return envelope({"styles": [style_service.style_dto(row) for row in rows]}, request=request)


@router.get("/api/styles/{style_key}")
async def get_style(
    style_key: str,
    version: int | None = Query(default=None),
    user: AppUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    await style_service.seed_styles(session)
    definition = await style_service.get_style(session, style_key, version)
    if definition is None:
        from app.core.errors import not_found

        raise not_found("error.not_found.style")
    return envelope(style_service.style_dto(definition), request=request)


@router.put("/api/projects/{project_id}/style")
async def select_style(
    project_id: UUID,
    payload: StyleSelectRequest,
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
        scope_key=f"project:{project.id}:style:select",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    if not await _plan_complete(session, project):
        raise gate("error.gate.plan_incomplete")

    await style_service.seed_styles(session)
    definition = await style_service.get_style(session, payload.style_key, payload.style_version)
    if definition is None:
        raise validation(
            "error.validation.unknown_style",
            {"styleKey": payload.style_key, "styleVersion": payload.style_version},
        )

    design_pages = await _design_page_ids(session, project)
    selection = StyleSelection(
        id=new_id(),
        project_id=project.id,
        style_definition_id=definition.id,
        style_version=definition.version,
        confirmed_at=None,
        remember_preference=bool(payload.remember_preference),
        version=1,
        created_at=utcnow(),
    )
    session.add(selection)
    await session.flush()
    project.current_style_selection_id = selection.id
    bump_project(project)
    await session.flush()

    if design_pages:
        await events.append(
            session,
            project.id,
            "staleChanged",
            {
                "fromStage": Stage.STYLE.value,
                "cause": "STYLE_CHANGE",
                "affectedPageIds": [str(pid) for pid in design_pages],
                "affectedPages": len(set(design_pages)),
                "rerunPages": len(design_pages),
                "cascadeRatio": 1.0,
                "projectVersion": project.version,
            },
        )
    await emit_stage_state(session, project)

    data = {"styleSelection": style_service.selection_dto(selection, definition)}
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="style_selection",
        resource_id=selection.id,
    )
    await session.commit()
    return response


@router.post("/api/projects/{project_id}/style/confirm")
async def confirm_style(
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
        scope_key=f"project:{project.id}:style:confirm",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    selection, definition = await state.load_style_selection(session, project)
    if selection is None or definition is None:
        raise gate("error.gate.style_not_selected")
    if not await _plan_complete(session, project):
        raise gate("error.gate.plan_incomplete")

    if selection.confirmed_at is None:
        selection.confirmed_at = utcnow()
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project)

    snapshot = await state.build_snapshot(session, project)
    stage = next((item for item in snapshot.stages if item.stage == Stage.STYLE.value), None)
    if stage is None:
        raise gate("error.gate.style_not_selected")
    data = {
        "styleSelection": style_service.selection_dto(selection, definition),
        "stage": stage,
        "stale": None,
    }
    response = envelope(
        data,
        ctx=ctx,
        project_version=project.version,
        sequence=snapshot.sequence,
    )
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="style_selection",
        resource_id=selection.id,
    )
    await session.commit()
    return response
