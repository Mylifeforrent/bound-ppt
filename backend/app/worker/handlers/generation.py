"""Generation job handlers (OUTLINE, PLAN_PAGE, DESIGN_PAGE).

Imported by app.worker.handlers. Content never enters durable events or logs;
the committed outline/plan/design bodies live in object storage only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select

from app.core.idempotency import bump_project
from app.core.ids import digest_json, new_id, utcnow
from app.domain.enums import ArtifactKind, HistoryReason, JobType, PageType
from app.models import (
    ArtifactVersion,
    OutlinePageVersion,
    OutlineSectionVersion,
    OutlineVersion,
    Page,
    Project,
)
from app.services import artifacts, generation, state
from app.services import styles as style_service
from app.services.events import events
from app.services.stages import emit_stage_state, emit_stale_changed
from app.worker.runner import JobContext, JobFailure, register

_REASON: dict[str, str] = {
    "TWEAK": HistoryReason.TWEAK.value,
    "REPLAN": HistoryReason.REPLAN.value,
    "REGENERATE": HistoryReason.REGENERATE.value,
    "RETRY": HistoryReason.REGENERATE.value,
}


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            value = obj.get(name)
            if value is not None:
                return value
        return default
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _reason(value: Any) -> str:
    return _REASON.get(str(value or "").upper(), HistoryReason.MANUAL.value)


async def _load_project(ctx: JobContext) -> Project:
    project = await ctx.session.get(Project, ctx.project_id)
    if project is None:
        raise JobFailure("project_missing", category="not_found", message_key="error.not_found.project")
    return project


async def _current_body(
    session: Any, project: Project, page_id: UUID, kind: str
) -> tuple[ArtifactVersion | None, dict[str, Any] | None]:
    pointer = await artifacts.pointer_for(session, project, page_id, kind)
    if pointer is None:
        return None, None
    version = await session.get(ArtifactVersion, pointer.artifact_version_id)
    if version is None:
        return None, None
    return version, await artifacts.read_artifact_body(version)


def _plan_payload(project: Project, page: OutlinePageVersion, audience: str) -> dict[str, Any]:
    return {
        "pageId": str(page.page_id),
        "position": page.position,
        "pageType": page.page_type,
        "sectionKey": page.section_key,
        "title": page.title,
        "keyPoints": list(page.key_points or []),
        "audience": audience,
    }


# ---- OUTLINE ---------------------------------------------------------------


@register(JobType.OUTLINE)
async def outline_job(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await _load_project(ctx)
    profile = await state.load_profile(ctx.session, project)
    if profile is None or await state.compute_profile_dirty(ctx.session, project, profile):
        raise JobFailure("profile_dirty", category="gate_violation", message_key="error.gate.profile_dirty")
    answers = await generation.load_answers(ctx.session, project)
    digests = await generation.load_digests_payload(ctx.session, project)
    sources = await generation.load_sources_payload(ctx.session, project)

    await ctx.check_cancel()
    result = await ctx.gateway.outline(
        topic=project.topic,
        profile=generation.profile_payload(profile),
        digests=digests,
        sources=sources,
        answers=answers,
    )
    await ctx.check_cancel()

    value = result.value
    sections: list[dict[str, str]] = []
    section_titles: dict[str, str] = {}

    def add_section(raw_key: Any, raw_title: Any = None) -> str:
        key = generation.slug(str(raw_key or "body"))
        if key not in section_titles:
            title = str(raw_title or "").strip() or key.replace("-", " ").title()
            section_titles[key] = title[:80]
            sections.append({"key": key, "title": section_titles[key]})
        return key

    for raw in _get(value, "sections", default=[]) or []:
        add_section(_get(raw, "section_key", "sectionKey"), _get(raw, "title"))
    if not sections:
        add_section("body", "Body")

    body_specs: list[dict[str, Any]] = []
    for raw in _get(value, "pages", default=[]) or []:
        title = str(_get(raw, "title") or "").strip()
        if not title:
            continue
        section_key = add_section(
            _get(raw, "section_key", "sectionKey") or sections[0]["key"],
            _get(raw, "section_title", "sectionTitle"),
        )
        points = [
            str(point).strip()
            for point in (_get(raw, "key_points", "keyPoints") or [])
            if str(point).strip()
        ][:4]
        body_specs.append({"title": title[:120], "section_key": section_key, "key_points": points})
    if not body_specs:
        body_specs.append(
            {"title": project.topic[:120], "section_key": sections[0]["key"], "key_points": []}
        )

    max_total = max(3, int(ctx.settings.page_max_count))
    body_limit = max(0, max_total - 3)
    body_specs = body_specs[:body_limit] if body_limit else []
    if not body_specs:
        body_specs = [{"title": project.topic[:120], "section_key": sections[0]["key"], "key_points": []}]

    specs: list[dict[str, Any]] = [
        {
            "page_type": PageType.COVER.value,
            "section_key": sections[0]["key"],
            "title": (project.name or project.topic)[:120],
            "key_points": [project.topic] if project.topic else [],
        },
        {
            "page_type": PageType.TOC.value,
            "section_key": sections[0]["key"],
            "title": "Contents",
            "key_points": [section["title"] for section in sections][:8],
        },
    ]
    for spec in body_specs:
        specs.append({"page_type": PageType.BODY.value, **spec})
    specs.append(
        {
            "page_type": PageType.END.value,
            "section_key": sections[-1]["key"],
            "title": "Thank you",
            "key_points": [],
        }
    )

    max_version = await ctx.session.scalar(
        select(func.max(OutlineVersion.version)).where(OutlineVersion.project_id == project.id)
    )
    version_no = int(max_version or 0) + 1
    fingerprint = digest_json(
        {
            "topic": project.topic,
            "profileId": str(profile.id),
            "profileFingerprint": profile.input_fingerprint,
            "pages": specs,
        }
    )
    outline = OutlineVersion(
        id=new_id(),
        project_id=project.id,
        version=version_no,
        confirmed_at=None,
        confirmed_by_user_id=None,
        input_fingerprint=fingerprint,
        producer_job_id=ctx.job.id,
        schema_version=1,
        created_at=utcnow(),
    )
    ctx.session.add(outline)
    await ctx.session.flush()

    for position, section in enumerate(sections, start=1):
        ctx.session.add(
            OutlineSectionVersion(
                id=new_id(),
                outline_version_id=outline.id,
                section_key=section["key"],
                title=section["title"],
                position=position,
            )
        )
    page_rows: list[tuple[Page, OutlinePageVersion]] = []
    for position, spec in enumerate(specs, start=1):
        page = Page(
            id=new_id(),
            project_id=project.id,
            page_type=spec["page_type"],
            created_at=utcnow(),
        )
        ctx.session.add(page)
        await ctx.session.flush()
        outline_page = OutlinePageVersion(
            id=new_id(),
            outline_version_id=outline.id,
            page_id=page.id,
            position=position,
            section_key=spec["section_key"],
            title=spec["title"],
            page_type=spec["page_type"],
            key_points=list(spec["key_points"]),
            created_at=utcnow(),
        )
        ctx.session.add(outline_page)
        page_rows.append((page, outline_page))
    await ctx.session.flush()

    project.current_outline_version_id = outline.id
    bump_project(project)
    await ctx.session.flush()

    chunk = 0
    for section in sections:
        chunk += 1
        await ctx.emit_ephemeral(
            {
                "type": "outlineDelta",
                "jobId": str(ctx.job.id),
                "chunkIndex": chunk,
                "delta": {"section": {"sectionKey": section["key"], "title": section["title"]}},
            }
        )
    for page, outline_page in page_rows:
        chunk += 1
        await ctx.emit_ephemeral(
            {
                "type": "outlineDelta",
                "jobId": str(ctx.job.id),
                "chunkIndex": chunk,
                "delta": {
                    "page": {
                        "pageId": str(page.id),
                        "position": outline_page.position,
                        "pageType": outline_page.page_type,
                        "sectionKey": outline_page.section_key,
                        "title": outline_page.title,
                        "keyPoints": list(outline_page.key_points or []),
                    }
                },
            }
        )

    await events.append(
        ctx.session,
        project.id,
        "outlineDone",
        {
            "outlineVersionId": str(outline.id),
            "version": outline.version,
            "pageCount": len(specs),
            "sectionCount": len(sections),
            "deviation": len(specs) - int(profile.page_count),
            "projectVersion": project.version,
        },
    )
    await emit_stage_state(ctx.session, project)
    await ctx.usage(
        capability="outline",
        unit_type="deck",
        quantity=1,
        provider=result.usage.provider,
        estimated_cost=result.usage.estimated_cost,
        stage="OUTLINE",
    )
    await ctx.check_cancel()
    await ctx.session.flush()


# ---- PLAN_PAGE -------------------------------------------------------------


@register(JobType.PLAN_PAGE)
async def plan_page_job(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await _load_project(ctx)
    page_id = _page_id(ctx)
    bundle = await state.load_outline(ctx.session, project)
    outline_page = bundle.by_page.get(page_id)
    page = await ctx.session.get(Page, page_id)
    if bundle.version is None or outline_page is None or page is None:
        raise JobFailure("artifact_missing", category="not_found", message_key="error.not_found.artifact")
    if page.retired_at is not None:
        raise JobFailure(
            "page_retired", category="conflict", message_key="error.conflict.stale_version", retryable=False
        )

    profile = await state.load_profile(ctx.session, project)
    sources = await generation.load_sources_payload(ctx.session, project)
    reason = _reason(ctx.payload.get("reason"))
    instruction = None
    if ctx.job.instruction_ref:
        instruction = await artifacts.read_text_ref(ctx.job.instruction_ref)
    is_tweak = reason in {HistoryReason.TWEAK.value} and bool(instruction)
    _current_version, current_body = await _current_body(
        ctx.session, project, page_id, ArtifactKind.PLAN.value
    )

    await ctx.check_cancel()
    if is_tweak and current_body is not None:
        result = await ctx.gateway.tweak(
            body=generation.plan_for_model(current_body),
            instruction=instruction or "",
            kind=ArtifactKind.PLAN.value,
        )
    else:
        variant = await generation.next_variant(ctx.session, project, page_id, ArtifactKind.PLAN.value)
        result = await ctx.gateway.plan_page(
            page=_plan_payload(project, outline_page, profile.audience if profile else ""),
            sources=sources,
            variant=variant,
        )
    await ctx.check_cancel()

    raw = generation.body_to_dict(result.value)
    body = generation.normalize_plan_body(
        raw,
        title=outline_page.title,
        page_type=outline_page.page_type,
        position=outline_page.position,
    )
    fingerprint = generation.expected_plan_fingerprint(project, outline_page)
    source_ids = [str(source["id"]) for source in sources][:8]
    design_pointer = await artifacts.pointer_for(
        ctx.session, project, page_id, ArtifactKind.DESIGN.value
    )
    version = await artifacts.commit_artifact(
        ctx.session,
        project,
        page,
        ArtifactKind.PLAN.value,
        body,
        fingerprint,
        source_refs=source_ids,
        producer_job_id=ctx.job.id,
        producer_attempt_id=ctx.attempt_id,
        producer_model=result.usage.model_id,
        prompt_version="plan@1",
        reason=reason,
        upstream_refs={
            "outlineVersionId": str(bundle.version.id),
            "outlinePageVersionId": str(outline_page.id),
            "profileVersionId": str(profile.id) if profile is not None else None,
        },
    )
    depth = await artifacts._active_depth(ctx.session, project, page_id, ArtifactKind.PLAN.value)
    await events.append(
        ctx.session,
        project.id,
        "pageJobDone",
        {
            "jobId": str(ctx.job.id),
            "pageId": str(page_id),
            "kind": ArtifactKind.PLAN.value,
            "artifactVersionId": str(version.id),
            "version": version.version,
            "historyDepth": depth,
            "projectVersion": project.version,
        },
    )
    if design_pointer is not None:
        await emit_stale_changed(
            ctx.session,
            project,
            from_stage="PLAN",
            cause="PAGE_TWEAK" if is_tweak else "PAGE_REPLAN",
            affected_plan=[],
            affected_design=[page_id],
            changed_pages=1,
        )
    await emit_stage_state(ctx.session, project)
    await ctx.usage(
        capability="plan",
        unit_type="page",
        quantity=1,
        provider=result.usage.provider,
        estimated_cost=result.usage.estimated_cost,
        stage="PLAN",
        page_id=page_id,
    )
    await ctx.check_cancel()
    await ctx.session.flush()


# ---- DESIGN_PAGE -----------------------------------------------------------


@register(JobType.DESIGN_PAGE)
async def design_page_job(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await _load_project(ctx)
    page_id = _page_id(ctx)
    bundle = await state.load_outline(ctx.session, project)
    outline_page = bundle.by_page.get(page_id)
    page = await ctx.session.get(Page, page_id)
    if bundle.version is None or outline_page is None or page is None:
        raise JobFailure("artifact_missing", category="not_found", message_key="error.not_found.artifact")
    if page.retired_at is not None:
        raise JobFailure(
            "page_retired", category="conflict", message_key="error.conflict.stale_version", retryable=False
        )

    plan_version, plan_body = await _current_body(ctx.session, project, page_id, ArtifactKind.PLAN.value)
    if plan_version is None or plan_body is None:
        raise JobFailure("plan_missing", category="gate_violation", message_key="error.gate.plan_incomplete")
    selection, definition = await state.load_style_selection(ctx.session, project)
    if selection is None or definition is None:
        raise JobFailure("style_missing", category="gate_violation", message_key="error.gate.style_not_selected")
    if not selection.confirmed_at:
        raise JobFailure(
            "style_unconfirmed", category="gate_violation", message_key="error.gate.style_unconfirmed"
        )
    try:
        theme = style_service.theme_json(definition)
    except KeyError as exc:
        raise JobFailure(
            "style_missing", category="gate_violation", message_key="error.validation.unknown_style"
        ) from exc

    reason = _reason(ctx.payload.get("reason"))
    instruction = None
    if ctx.job.instruction_ref:
        instruction = await artifacts.read_text_ref(ctx.job.instruction_ref)
    is_tweak = reason in {HistoryReason.TWEAK.value} and bool(instruction)
    _design_version, current_design = await _current_body(
        ctx.session, project, page_id, ArtifactKind.DESIGN.value
    )

    await ctx.check_cancel()
    if is_tweak and current_design is not None:
        result = await ctx.gateway.tweak(
            body=generation.design_for_model(current_design),
            instruction=instruction or "",
            kind=ArtifactKind.DESIGN.value,
        )
    else:
        variant = await generation.next_variant(ctx.session, project, page_id, ArtifactKind.DESIGN.value)
        result = await ctx.gateway.design_page(
            plan=generation.plan_for_model(plan_body),
            style_key=definition.key,
            variant=variant,
        )
    await ctx.check_cancel()

    raw = generation.body_to_dict(result.value)
    body = generation.normalize_design_body(
        raw,
        title=outline_page.title,
        page_type=outline_page.page_type,
        position=outline_page.position,
        style_key=definition.key,
        style_version=selection.style_version,
        theme_data=theme,
    )
    fingerprint = generation.expected_design_fingerprint(
        project, outline_page, plan_version, selection, definition
    )
    chrome, _label = generation.page_chrome(outline_page, bundle)
    source_ids = [str(source_id) for source_id in (plan_body.get("meta") or {}).get("sourceIds") or []]
    version = await artifacts.commit_artifact(
        ctx.session,
        project,
        page,
        ArtifactKind.DESIGN.value,
        body,
        fingerprint,
        source_refs=source_ids,
        producer_job_id=ctx.job.id,
        producer_attempt_id=ctx.attempt_id,
        producer_model=result.usage.model_id,
        prompt_version="design@1",
        reason=reason,
        upstream_refs={
            "planArtifactVersionId": str(plan_version.id),
            "outlineVersionId": str(bundle.version.id),
            "outlinePageVersionId": str(outline_page.id),
            "styleDefinitionId": str(definition.id),
            "chromeVersion": chrome,
        },
    )
    depth = await artifacts._active_depth(ctx.session, project, page_id, ArtifactKind.DESIGN.value)
    await events.append(
        ctx.session,
        project.id,
        "pageJobDone",
        {
            "jobId": str(ctx.job.id),
            "pageId": str(page_id),
            "kind": ArtifactKind.DESIGN.value,
            "artifactVersionId": str(version.id),
            "version": version.version,
            "historyDepth": depth,
            "projectVersion": project.version,
        },
    )
    await emit_stage_state(ctx.session, project)
    await ctx.usage(
        capability="design",
        unit_type="page",
        quantity=1,
        provider=result.usage.provider,
        estimated_cost=result.usage.estimated_cost,
        stage="DESIGN",
        page_id=page_id,
    )
    await ctx.check_cancel()
    await ctx.session.flush()


def _page_id(ctx: JobContext) -> UUID:
    raw = ctx.payload.get("pageId")
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError) as exc:
        raise JobFailure("page_missing", category="validation", message_key="error.validation.invalid_request") from exc


# Export handler registration lives in its own module; import it so that the
# package import in worker startup registers every handler.
import app.worker.handlers.export  # noqa: E402,F401
