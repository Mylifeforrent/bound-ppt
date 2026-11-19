from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    CommandContext,
    command_context,
    envelope,
    load_owned_project,
    replay_response,
)
from app.core.db import get_session
from app.core.errors import conflict, gate, validation
from app.core.idempotency import begin_command, bump_project, finish_command
from app.core.ids import iso, new_id, utcnow
from app.llm.gateway import gateway
from app.models import (
    GapDecision,
    InterviewAnswer,
    RequirementsProfile,
)
from app.schemas.dto import (
    AnswerRequest,
    AnswerResultDTO,
    GapDecisionRequest,
    GapDecisionResultDTO,
    GapSearchOutcomeDTO,
    ProfileResultDTO,
    ResearchStartDTO,
)
from app.services import materials as material_service
from app.services import research as research_service
from app.services.events import events
from app.services.jobs import wake_jobs
from app.services.stages import emit_stage_state, emit_stale_changed
from app.services.state import (
    build_snapshot,
    compute_profile_dirty,
    load_outline,
    load_profile,
    make_stale_summary,
)

router = APIRouter(prefix="/api/projects/{project_id}", tags=["research"])


@router.get("/research")
async def get_research(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    state = await research_service.build_research_state(session, project)
    return envelope(state, ctx=ctx, project_version=project.version)


@router.get("/sources")
async def get_sources(
    project_id: UUID,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    panel = await research_service.build_source_panel(session, project)
    return envelope(panel, ctx=ctx, project_version=project.version)


@router.post("/research/start", status_code=202)
async def start_research(
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
        scope_key=f"project:{project.id}:research:start",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_project_active(project)
    if project.stage not in ("INTAKE", "RESEARCH"):
        raise gate("error.gate.material_locked", {"restartRequired": True})

    _questions, created = await research_service.ensure_questions(session, project)
    transitioned = project.stage != "RESEARCH"
    if transitioned:
        project.stage = "RESEARCH"
    if transitioned or created:
        bump_project(project)
        await session.flush()
    for question in created:
        await events.append(
            session,
            project.id,
            "questionAsked",
            {
                "questionKey": question.question_key,
                "position": question.position,
                "optionKeys": research_service.option_keys(question),
            },
        )

    jobs = []
    materials = await material_service.list_active_materials(session, project)
    if materials:
        missing = await material_service.materials_missing_digest(session, project)
        for material in missing:
            jobs.append(await material_service.enqueue_digest(session, project, material))
        if not missing and await research_service.all_materials_digested(session, project):
            if await research_service.latest_gap_batch(session, project) is None:
                jobs.append(await research_service.enqueue_gap_suggest(session, project))
    else:
        jobs.extend(await research_service.enqueue_web_only_searches(session, project))

    if transitioned:
        await session.flush()
        await emit_stage_state(session, project, previous_status="AVAILABLE")

    snapshot = await build_snapshot(session, project)
    stage_state = next((s for s in snapshot.stages if s.stage == project.stage), None)
    dto = ResearchStartDTO(
        stage=project.stage,
        stage_status=stage_state.status if stage_state else "IN_PROGRESS",
        job_ids=[job.id for job in jobs],
    )
    response = envelope(dto, ctx=ctx, project_version=project.version, status_code=202)
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=project.id,
    )
    await session.commit()
    if jobs:
        wake_jobs(*jobs)
    return response


@router.put("/research/answers/{question_key}")
async def put_answer(
    project_id: UUID,
    question_key: str,
    payload: AnswerRequest,
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
        scope_key=f"project:{project.id}:research:answer:{question_key}",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_project_active(project)
    research_service.assert_research_started(project)

    questions = await research_service.load_questions(session, project)
    question = next((q for q in questions if q.question_key == question_key), None)
    if question is None:
        raise validation("error.validation.unknown_question")
    if payload.option_key not in research_service.option_keys(question):
        raise validation("error.validation.unknown_option")

    answer = await session.scalar(
        select(InterviewAnswer).where(InterviewAnswer.question_id == question.id)
    )
    if answer is None:
        answer = InterviewAnswer(
            id=new_id(),
            project_id=project.id,
            question_id=question.id,
            option_key=payload.option_key,
            revision=1,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(answer)
    else:
        answer.option_key = payload.option_key
        answer.revision += 1
        answer.updated_at = utcnow()
    await session.flush()

    profile = await load_profile(session, project)
    dirty = await compute_profile_dirty(session, project, profile) if profile else False
    bump_project(project)
    await session.flush()
    await events.append(
        session,
        project.id,
        "answerRecorded",
        {
            "questionKey": question.question_key,
            "optionKey": answer.option_key,
            "revision": answer.revision,
            "profileDirty": dirty,
        },
    )

    dto = AnswerResultDTO(
        question={
            "key": question.question_key,
            "optionKey": answer.option_key,
            "revision": answer.revision,
            "answeredAt": iso(answer.updated_at),
        },
        profile_dirty=dirty,
        stale=None,
    )
    response = envelope(dto, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="interview_answer",
        resource_id=answer.id,
    )
    await session.commit()
    return response


@router.post("/research/gaps/decisions", status_code=202)
async def decide_gaps(
    project_id: UUID,
    payload: GapDecisionRequest,
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
    request: Request = None,
):
    key = ctx.require_idempotency()
    expected_version = ctx.require_version()
    project = await load_owned_project(session, project_id, ctx.user)
    payload_dict = payload.model_dump(mode="json")
    replay, record = await begin_command(
        session,
        scope_key=f"project:{project.id}:research:gaps:decisions",
        key=key,
        payload=payload_dict,
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_project_active(project)
    research_service.assert_research_started(project)
    await research_service.assert_digest_complete(session, project)

    gap = await research_service.load_gap_context(session, project)
    if gap.batch is None or not gap.suggestions:
        raise gate("error.gate.digest_incomplete")
    if gap.decided:
        raise gate("error.gate.gaps_already_decided")

    by_id = {suggestion.id: suggestion for suggestion in gap.suggestions}
    selected_ids = list(dict.fromkeys(payload.selected_suggestion_ids))
    if any(gap_id not in by_id for gap_id in selected_ids):
        raise validation("error.validation.gap_selection_invalid")
    if payload.web_skipped and selected_ids:
        raise validation("error.validation.gap_selection_invalid")
    if not payload.web_skipped and not selected_ids:
        raise validation("error.validation.gap_selection_invalid")

    selected_set = set(selected_ids)
    now = utcnow()
    for suggestion in gap.suggestions:
        selected = suggestion.id in selected_set
        suggestion.status = research_service.gap_status_for(selected)
        session.add(
            GapDecision(
                id=new_id(),
                project_id=project.id,
                gap_suggestion_id=suggestion.id,
                selected=selected,
                decided_at=now,
            )
        )
    await session.flush()

    search_jobs = []
    query_index = 0
    for suggestion in gap.suggestions:
        if suggestion.id not in selected_set:
            continue
        query_index += 1
        search_jobs.append(
            await research_service.enqueue_gap_search(session, project, suggestion, query_index)
        )

    bump_project(project)
    await session.flush()
    await events.append(
        session,
        project.id,
        "gapDecided",
        {
            "batch": gap.batch,
            "selectedCount": len(selected_ids),
            "suggestedCount": len(gap.suggestions),
            "webSkipped": payload.web_skipped,
        },
    )

    refreshed = await research_service.load_gap_context(session, project)
    gaps_dto = research_service.gap_state_dto(refreshed)
    if gaps_dto is None:
        raise conflict("error.conflict.stage_changed")
    dto = GapDecisionResultDTO(
        gaps=gaps_dto,
        search_job_ids=[job.id for job in search_jobs],
        gap_searches=[
            GapSearchOutcomeDTO(
                gap_suggestion_id=outcome.gap_suggestion_id,
                query_index=outcome.query_index,
                outcome=outcome.outcome,
                result_count=outcome.result_count,
                error_code=outcome.error_code,
            )
            for outcome in await research_service.build_gap_searches(session, project, refreshed)
        ],
        web_skipped=payload.web_skipped,
    )
    response = envelope(dto, ctx=ctx, project_version=project.version, status_code=202)
    finish_command(
        record,
        status_code=202,
        response=json.loads(response.body),
        resource_type="project",
        resource_id=project.id,
    )
    await session.commit()
    if search_jobs:
        wake_jobs(*search_jobs)
    return response


@router.post("/research/profile")
async def refresh_profile(
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
        scope_key=f"project:{project.id}:research:profile",
        key=key,
        payload={},
        project=project,
        expected_version=expected_version,
    )
    if replay is not None:
        return replay_response(replay, request)

    await material_service.assert_project_active(project)
    research_service.assert_research_started(project)
    inputs = await research_service.build_profile_inputs(session, project)
    if len(inputs.answers) < len(research_service.QUESTION_CATALOG):
        raise gate("error.gate.answers_incomplete")
    if inputs.materials and not inputs.gap.decided:
        raise gate("error.gate.gaps_undecided")

    profile = await load_profile(session, project)
    dirty = bool(profile and profile.input_fingerprint != inputs.fingerprint)
    if profile is not None and not dirty:
        outline = await load_outline(session, project)
        dto = ProfileResultDTO(
            profile=research_service.profile_dto(profile),
            profile_dirty=False,
            outline_unconfirmed=bool(outline.version and not outline.confirmed),
            stale=None,
        )
        response = envelope(dto, ctx=ctx, project_version=project.version)
        finish_command(
            record,
            status_code=200,
            response=json.loads(response.body),
            resource_type="profile",
            resource_id=profile.id,
        )
        await session.commit()
        return response

    # Close the admission transaction so the provider call never holds DB locks.
    await session.commit()
    try:
        result = await gateway.profile(
            topic=project.topic,
            answers=inputs.answer_payload,
            digests=inputs.digests,
            sources=research_service.gateway_sources(inputs.sources),
            web_skipped=inputs.web_skipped,
        )
    except Exception:
        if record is not None:
            await session.delete(record)
            await session.commit()
        raise

    project = await load_owned_project(session, project_id, ctx.user)
    await session.refresh(project)
    if project.version != expected_version:
        if record is not None:
            await session.delete(record)
            await session.commit()
        raise conflict("error.conflict.stale_version", {"currentVersion": project.version})
    refreshed_inputs = await research_service.build_profile_inputs(session, project)
    if refreshed_inputs.fingerprint != inputs.fingerprint:
        if record is not None:
            await session.delete(record)
            await session.commit()
        raise conflict("error.conflict.stale_version", {"currentVersion": project.version})

    outline = await load_outline(session, project)
    outline_existed = outline.version is not None
    had_profile = profile is not None
    web_sources = await research_service.web_source_count(session, project)
    version = await research_service.next_profile_version(session, project)
    profile_row = RequirementsProfile(
        id=new_id(),
        project_id=project.id,
        version=version,
        audience=str(result.value.audience),
        goal=str(result.value.goal),
        style_mood=str(result.value.style_mood),
        page_count=research_service.clamp_page_count(result.value.page_count),
        materials_summary=research_service.materials_summary_payload(refreshed_inputs),
        web_scope=research_service.web_scope_payload(refreshed_inputs, web_sources),
        web_skipped=refreshed_inputs.web_skipped,
        content_strategy=str(result.value.content_strategy),
        source_refs=[str(source.id) for source in refreshed_inputs.sources],
        input_fingerprint=refreshed_inputs.fingerprint,
        producer_job_id=None,
    )
    session.add(profile_row)
    await session.flush()
    project.current_profile_version_id = profile_row.id
    if outline.version is not None and outline.version.confirmed_at is not None:
        outline.version.confirmed_at = None
        outline.version.confirmed_by_user_id = None
    bump_project(project)
    await session.flush()

    outline_unconfirmed = outline.version is not None
    if had_profile:
        await events.append(
            session,
            project.id,
            "profileUpdated",
            {
                "profileVersion": profile_row.version,
                "profileVersionId": str(profile_row.id),
                "outlineUnconfirmed": outline_unconfirmed,
                "projectVersion": project.version,
            },
        )
    else:
        await events.append(
            session,
            project.id,
            "profileReady",
            {
                "profileVersion": profile_row.version,
                "profileVersionId": str(profile_row.id),
                "materialsCount": len(refreshed_inputs.materials),
                "webSourceCount": web_sources,
                "webSkipped": refreshed_inputs.web_skipped,
                "projectVersion": project.version,
            },
        )

    stale = None
    if outline_existed:
        page_ids = [page.page_id for page in outline.pages]
        stale = make_stale_summary(
            project, "PROFILE_UPDATE", plan_pages=page_ids, design_pages=list(page_ids)
        )
        await emit_stale_changed(
            session,
            project,
            from_stage="RESEARCH",
            cause="PROFILE_UPDATE",
            affected_plan=page_ids,
            affected_design=list(page_ids),
            changed_pages=len(page_ids),
        )

    dto = ProfileResultDTO(
        profile=research_service.profile_dto(profile_row),
        profile_dirty=False,
        outline_unconfirmed=outline_unconfirmed,
        stale=stale,
    )
    response = envelope(dto, ctx=ctx, project_version=project.version)
    finish_command(
        record,
        status_code=200,
        response=json.loads(response.body),
        resource_type="profile",
        resource_id=profile_row.id,
    )
    await session.commit()
    return response
