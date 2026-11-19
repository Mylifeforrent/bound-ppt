from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    load_owned_project,
    replay_response,
)
from app.core.db import get_session
from app.core.errors import conflict, gate, not_found, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.core.ids import new_id, utcnow
from app.domain.enums import (
    STAGE_ORDER,
    ArtifactKind,
    JobType,
    PageType,
    ProjectMode,
    Stage,
    StageStatus,
)
from app.models import (
    ArtifactLineage,
    ArtifactPointer,
    ArtifactSourceRef,
    ArtifactVersion,
    OutlinePageVersion,
    Page,
    PageHistoryEntry,
    Project,
)
from app.schemas.dto import (
    AdvanceRequest,
    AdvanceResultDTO,
    OutlineConfirmResultDTO,
    OutlineEditRequest,
    OutlineEditResultDTO,
    OutlineInsertRequest,
    OutlineInsertResultDTO,
    OutlineMoveRequest,
)
from app.services import generation, state
from app.services import projects as project_service
from app.services.advance import validate_advance_token
from app.services.events import events
from app.services.jobs import enqueue_job, find_active, wake_jobs
from app.services.stages import emit_stage_state

router = APIRouter(tags=["outline"])


# ---- Helpers ---------------------------------------------------------------


async def _bundle(session: AsyncSession, project: Project) -> state.OutlineBundle:
    bundle = await state.load_outline(session, project)
    if bundle.version is None:
        raise gate("error.gate.outline_missing")
    return bundle


def _page_row(bundle: state.OutlineBundle, page_id: UUID) -> OutlinePageVersion:
    page = bundle.by_page.get(page_id)
    if page is None:
        raise not_found("error.not_found.outline")
    return page


def _require_section(bundle: state.OutlineBundle, section_key: str) -> str:
    if section_key not in bundle.section_titles:
        raise validation("error.validation.unknown_section", {"sectionKey": section_key})
    return bundle.section_titles[section_key]


def _unconfirm(bundle: state.OutlineBundle) -> None:
    if bundle.version is None:
        return
    bundle.version.confirmed_at = None
    bundle.version.confirmed_by_user_id = None


async def _apply_order(session: AsyncSession, version_id: UUID, ordered_ids: list[UUID]) -> None:
    rows = list(
        (
            await session.scalars(
                select(OutlinePageVersion).where(OutlinePageVersion.outline_version_id == version_id)
            )
        ).all()
    )
    by_id = {row.page_id: row for row in rows}
    if set(by_id) != set(ordered_ids):
        raise not_found("error.not_found.outline")
    # Two passes keep the (outline_version_id, position) unique constraint satisfied.
    # The negative base is far from the small temporary positions used on insert.
    for index, page_id in enumerate(ordered_ids):
        by_id[page_id].position = -(1_000_000 + index)
    await session.flush()
    for index, page_id in enumerate(ordered_ids, start=1):
        by_id[page_id].position = index
    await session.flush()


def _section_append_index(ordered: list[OutlinePageVersion], bundle: state.OutlineBundle, section_key: str) -> int:
    section_positions = {section.section_key: section.position for section in bundle.sections}
    same_section = [index for index, page in enumerate(ordered) if page.section_key == section_key]
    if same_section:
        return same_section[-1] + 1
    target = section_positions.get(section_key, 10**6)
    for index, page in enumerate(ordered):
        if section_positions.get(page.section_key, 10**6) > target:
            return index
    return len(ordered)


def _insertion_index(
    remaining: list[OutlinePageVersion],
    bundle: state.OutlineBundle,
    *,
    section_key: str,
    before_page_id: UUID | None,
    to_position: int | None,
) -> int:
    if before_page_id is not None:
        for index, page in enumerate(remaining):
            if page.page_id == before_page_id:
                if page.section_key != section_key:
                    raise validation("error.validation.invalid_request", {"field": "beforePageId"})
                return index
        raise validation("error.validation.invalid_request", {"field": "beforePageId"})
    section_indices = [index for index, page in enumerate(remaining) if page.section_key == section_key]
    if to_position is not None:
        if to_position < 1:
            raise validation("error.validation.invalid_request", {"field": "toPosition"})
        if section_indices:
            if to_position <= len(section_indices):
                return section_indices[to_position - 1]
            return section_indices[-1] + 1
        return _section_append_index(remaining, bundle, section_key)
    return _section_append_index(remaining, bundle, section_key)


async def _stale_summary(
    session: AsyncSession,
    project: Project,
    *,
    cause: str,
    plan_pages: list[UUID],
    design_pages: list[UUID],
    changed_pages: int | None = None,
):
    summary = state.make_stale_summary(
        project,
        cause,
        plan_pages=plan_pages,
        design_pages=design_pages,
        changed_pages=changed_pages,
    )
    await events.append(
        session,
        project.id,
        "staleChanged",
        {
            "fromStage": Stage.OUTLINE.value,
            "cause": cause,
            "affectedPageIds": [str(pid) for pid in plan_pages + design_pages],
            "affectedPages": len(set(plan_pages) | set(design_pages)),
            "rerunPages": summary.rerun["plan"] + summary.rerun["design"],
            "cascadeRatio": summary.cascade_ratio,
            "projectVersion": project.version,
        },
    )
    return summary


# ---- Routes ----------------------------------------------------------------


@router.post("/api/projects/{project_id}/outline/generate", status_code=202)
async def generate_outline(
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
        scope_key=f"project:{project.id}:outline:generate",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    profile = await state.load_profile(session, project)
    if profile is None or await state.compute_profile_dirty(session, project, profile):
        raise gate("error.gate.profile_dirty")

    active = await find_active(session, f"outline:{project.id}")
    if active is not None:
        response = envelope(
            {"jobId": active.id, "outlineVersionId": None},
            ctx=ctx,
            project_version=project.version,
            idempotent_replay=True,
            status_code=200,
        )
        finish_command(
            record,
            status_code=200,
            response=json.loads(response.body),
            resource_type="job",
            resource_id=active.id,
        )
        await session.commit()
        return response

    job = await enqueue_job(
        session,
        project,
        JobType.OUTLINE,
        operation_key=f"outline:{project.id}",
        active_operation_key=f"outline:{project.id}",
        payload={},
        priority=5,
    )
    project.stage = Stage.OUTLINE.value
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project, previous_status=StageStatus.AVAILABLE.value)

    data = {"jobId": job.id, "outlineVersionId": None}
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


@router.get("/api/projects/{project_id}/outline")
async def get_outline(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    dto = await generation.build_outline_dto(session, project)
    return envelope(dto, ctx=ctx, project_version=project.version)


@router.post("/api/projects/{project_id}/outline/confirm")
async def confirm_outline(
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
        scope_key=f"project:{project.id}:outline:confirm",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    bundle = await _bundle(session, project)
    if not bundle.pages:
        raise gate("error.gate.outline_page_identity")
    seen: set[UUID] = set()
    for page in bundle.pages:
        if page.page_id in seen or page.page_type not in {item.value for item in PageType}:
            raise gate("error.gate.outline_page_identity")
        seen.add(page.page_id)
        row = await session.get(Page, page.page_id)
        if row is None or row.retired_at is not None or row.project_id != project.id:
            raise gate("error.gate.outline_page_identity")

    bundle.version.confirmed_at = utcnow()
    bundle.version.confirmed_by_user_id = ctx.user.id
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project)

    dto = await generation.build_outline_dto(session, project)
    snapshot = await state.build_snapshot(session, project)
    stage = next((item for item in snapshot.stages if item.stage == Stage.OUTLINE.value), None)
    if stage is None:
        raise gate("error.gate.outline_missing")
    data = OutlineConfirmResultDTO(outline=dto, stage=stage, snapshot=snapshot)
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
        resource_type="outline",
        resource_id=bundle.version.id,
    )
    await session.commit()
    return response


@router.patch("/api/projects/{project_id}/outline/pages/{page_id}")
async def edit_outline_page(
    project_id: UUID,
    page_id: UUID,
    payload: OutlineEditRequest,
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
        scope_key=f"project:{project.id}:outline:page:{page_id}:title",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    title = payload.title.strip()
    if not title:
        raise validation("error.validation.empty_title")
    bundle = await _bundle(session, project)
    page = _page_row(bundle, page_id)
    design_exists = (
        await session.scalar(
            select(ArtifactPointer.id).where(
                ArtifactPointer.project_id == project.id,
                ArtifactPointer.page_id == page_id,
                ArtifactPointer.kind == ArtifactKind.DESIGN.value,
            )
        )
        is not None
    )
    page.title = title
    _unconfirm(bundle)
    bump_project(project)
    await session.flush()

    design_pages = [page_id] if design_exists else []
    stale = await _stale_summary(
        session,
        project,
        cause="OUTLINE_EDIT",
        plan_pages=[],
        design_pages=design_pages,
        changed_pages=1,
    )
    await emit_stage_state(session, project)

    dto = await generation.build_outline_dto(session, project)
    data = OutlineEditResultDTO(outline=dto, stale=stale)
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="outline_page",
        resource_id=page_id,
    )
    await session.commit()
    return response


@router.post("/api/projects/{project_id}/outline/pages")
async def insert_outline_page(
    project_id: UUID,
    payload: OutlineInsertRequest,
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
        scope_key=f"project:{project.id}:outline:insert",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    title = payload.title.strip()
    if not title:
        raise validation("error.validation.empty_title")
    bundle = await _bundle(session, project)
    _require_section(bundle, payload.section_key)
    ordered = sorted(bundle.pages, key=lambda row: row.position)
    if payload.after_page_id is not None:
        match = next(
            (index for index, row in enumerate(ordered) if row.page_id == payload.after_page_id), None
        )
        if match is None or ordered[match].section_key != payload.section_key:
            raise validation("error.validation.invalid_request", {"field": "afterPageId"})
        insert_at = match + 1
    else:
        insert_at = _section_append_index(ordered, bundle, payload.section_key)

    page = Page(id=new_id(), project_id=project.id, page_type=PageType.BODY.value, created_at=utcnow())
    session.add(page)
    await session.flush()
    session.add(
        OutlinePageVersion(
            id=new_id(),
            outline_version_id=bundle.version.id,
            page_id=page.id,
            position=-(len(ordered) + 1),
            section_key=payload.section_key,
            title=title,
            page_type=PageType.BODY.value,
            key_points=[str(point) for point in payload.key_points],
            created_at=utcnow(),
        )
    )
    await session.flush()
    new_order = [row.page_id for row in ordered]
    new_order.insert(insert_at, page.id)
    await _apply_order(session, bundle.version.id, new_order)

    _unconfirm(bundle)
    bump_project(project)
    await session.flush()
    stale = await _stale_summary(
        session,
        project,
        cause="OUTLINE_INSERT",
        plan_pages=[page.id],
        design_pages=[page.id],
        changed_pages=1,
    )
    await emit_stage_state(session, project)

    dto = await generation.build_outline_dto(session, project)
    data = OutlineInsertResultDTO(outline=dto, page_id=page.id, stale=stale)
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="outline_page",
        resource_id=page.id,
    )
    await session.commit()
    return response


@router.delete("/api/projects/{project_id}/outline/pages/{page_id}")
async def delete_outline_page(
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
        scope_key=f"project:{project.id}:outline:page:{page_id}:delete",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    bundle = await _bundle(session, project)
    page_row = _page_row(bundle, page_id)
    if page_row.page_type != PageType.BODY.value:
        raise gate("error.gate.fixed_page_not_deletable")

    version_ids = list(
        (
            await session.scalars(
                select(ArtifactVersion.id).where(
                    ArtifactVersion.project_id == project.id,
                    ArtifactVersion.page_id == page_id,
                )
            )
        ).all()
    )
    if version_ids:
        await session.execute(
            delete(ArtifactSourceRef).where(ArtifactSourceRef.artifact_version_id.in_(version_ids))
        )
        await session.execute(
            delete(ArtifactLineage).where(ArtifactLineage.downstream_artifact_version_id.in_(version_ids))
        )
    await session.execute(
        delete(PageHistoryEntry).where(
            PageHistoryEntry.project_id == project.id, PageHistoryEntry.page_id == page_id
        )
    )
    await session.execute(
        delete(ArtifactPointer).where(
            ArtifactPointer.project_id == project.id, ArtifactPointer.page_id == page_id
        )
    )
    await session.execute(
        delete(ArtifactVersion).where(
            ArtifactVersion.project_id == project.id, ArtifactVersion.page_id == page_id
        )
    )
    await session.execute(
        delete(OutlinePageVersion).where(
            OutlinePageVersion.outline_version_id == bundle.version.id,
            OutlinePageVersion.page_id == page_id,
        )
    )
    page = await session.get(Page, page_id)
    if page is not None:
        page.retired_at = utcnow()
    await session.flush()

    remaining = [row.page_id for row in sorted(bundle.pages, key=lambda row: row.position) if row.page_id != page_id]
    await _apply_order(session, bundle.version.id, remaining)

    _unconfirm(bundle)
    bump_project(project)
    await session.flush()
    stale = await _stale_summary(
        session,
        project,
        cause="OUTLINE_DELETE",
        plan_pages=[page_id],
        design_pages=[page_id],
        changed_pages=1,
    )
    await emit_stage_state(session, project)

    dto = await generation.build_outline_dto(session, project)
    data = OutlineEditResultDTO(outline=dto, stale=stale)
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="outline_page",
        resource_id=page_id,
    )
    await session.commit()
    return response


@router.post("/api/projects/{project_id}/outline/pages/{page_id}/move")
async def move_outline_page(
    project_id: UUID,
    page_id: UUID,
    payload: OutlineMoveRequest,
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
        scope_key=f"project:{project.id}:outline:page:{page_id}:move",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    if payload.before_page_id is not None and payload.to_position is not None:
        raise validation("error.validation.invalid_request", {"fields": ["beforePageId", "toPosition"]})
    bundle = await _bundle(session, project)
    _require_section(bundle, payload.to_section_key)
    page_row = _page_row(bundle, page_id)
    ordered = sorted(bundle.pages, key=lambda row: row.position)
    remaining = [row for row in ordered if row.page_id != page_id]
    insert_at = _insertion_index(
        remaining,
        bundle,
        section_key=payload.to_section_key,
        before_page_id=payload.before_page_id,
        to_position=payload.to_position,
    )
    new_order = [row.page_id for row in remaining]
    new_order.insert(insert_at, page_id)
    old_order = [row.page_id for row in ordered]
    cross_section = page_row.section_key != payload.to_section_key
    page_row.section_key = payload.to_section_key
    await _apply_order(session, bundle.version.id, new_order)

    old_index = {pid: index for index, pid in enumerate(old_order)}
    design_pages = [pid for index, pid in enumerate(new_order) if old_index.get(pid) != index]
    if cross_section and page_id not in design_pages:
        design_pages.append(page_id)
    plan_pages = [page_id] if cross_section else []

    _unconfirm(bundle)
    bump_project(project)
    await session.flush()
    stale = await _stale_summary(
        session,
        project,
        cause="OUTLINE_MOVE",
        plan_pages=plan_pages,
        design_pages=design_pages,
        changed_pages=1,
    )
    await emit_stage_state(session, project)

    dto = await generation.build_outline_dto(session, project)
    data = OutlineEditResultDTO(outline=dto, stale=stale)
    response = envelope(data, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="outline_page",
        resource_id=page_id,
    )
    await session.commit()
    return response


@router.post("/api/projects/{project_id}/stages/advance")
async def advance_stage(
    project_id: UUID,
    payload: AdvanceRequest,
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
        scope_key=f"project:{project.id}:stages:advance",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    if project.mode != ProjectMode.FULLY_AUTOMATIC.value:
        raise gate("error.gate.auto_advance_ineligible")
    validate_advance_token(
        payload.advance_token,
        project_id=project.id,
        from_stage=payload.from_stage,
        stage_version=project.version,
    )
    if payload.from_stage != project.stage:
        raise conflict("error.conflict.stage_changed")

    snapshot = await state.build_snapshot(session, project)
    current = next((item for item in snapshot.stages if item.stage == payload.from_stage), None)
    if (
        current is None
        or not current.reachable
        or current.status in {StageStatus.LOCKED.value, StageStatus.IN_PROGRESS.value, StageStatus.ERROR.value}
    ):
        raise gate("error.gate.auto_advance_ineligible")
    stages = [stage.value for stage in STAGE_ORDER]
    index = stages.index(payload.from_stage)
    if index >= len(stages) - 1:
        raise gate("error.gate.auto_advance_ineligible")
    to_stage = stages[index + 1]

    # Fully-automatic outline advance is the implicit outline confirmation:
    # plan generation is gated on confirmed_at (PRD FR-3.10/FR-3.11; C-2).
    if payload.from_stage == Stage.OUTLINE.value:
        bundle = await state.load_outline(session, project)
        if bundle.version is not None and bundle.version.confirmed_at is None:
            from app.core.ids import utcnow

            bundle.version.confirmed_at = utcnow()
            bundle.version.confirmed_by_user_id = ctx.user.id
            await session.flush()

    project.stage = to_stage
    bump_project(project)
    await session.flush()
    await emit_stage_state(session, project)

    updated = await state.build_snapshot(session, project)
    result = AdvanceResultDTO(
        project=project_service.project_dto(project),
        stages=updated.stages,
        advanced=True,
        from_stage=payload.from_stage,
        to_stage=to_stage,
    )
    response = envelope(
        result,
        ctx=ctx,
        project_version=project.version,
        sequence=updated.sequence,
    )
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=project.id,
    )
    await session.commit()
    return response
