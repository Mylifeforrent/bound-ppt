from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ids import utcnow
from app.domain.enums import (
    STAGE_ORDER,
    JobState,
    PageStatus,
    ProjectMode,
    Stage,
    StageStatus,
)
from app.domain.fingerprints import chrome_version, design_fingerprint, plan_fingerprint, profile_fingerprint
from app.models import (
    ArtifactPointer,
    ArtifactVersion,
    GapDecision,
    GapSuggestion,
    InterviewAnswer,
    InterviewQuestion,
    Job,
    Material,
    OutlinePageVersion,
    OutlineSectionVersion,
    OutlineVersion,
    PageHistoryEntry,
    Project,
    ProjectEventCounter,
    RequirementsProfile,
    SourceItem,
    StyleDefinition,
    StyleSelection,
)
from app.schemas.dto import (
    ActiveJobRef,
    ArtifactStatus,
    PageCountsDTO,
    PageListDTO,
    PageSummaryDTO,
    ProjectDTO,
    ProjectSnapshotDTO,
    SnapshotCountsDTO,
    StageBlockerDTO,
    StageStateDTO,
    StaleSummaryDTO,
)
from app.services.advance import issue_advance_token


@dataclass
class OutlineBundle:
    version: OutlineVersion | None = None
    pages: list[OutlinePageVersion] = field(default_factory=list)
    sections: list[OutlineSectionVersion] = field(default_factory=list)

    @property
    def by_page(self) -> dict[UUID, OutlinePageVersion]:
        return {p.page_id: p for p in self.pages}

    @property
    def section_titles(self) -> dict[str, str]:
        return {s.section_key: s.title for s in self.sections}

    @property
    def confirmed(self) -> bool:
        return bool(self.version and self.version.confirmed_at)


async def load_outline(session: AsyncSession, project: Project) -> OutlineBundle:
    version: OutlineVersion | None = None
    if project.current_outline_version_id:
        version = await session.get(OutlineVersion, project.current_outline_version_id)
    if version is None:
        version = await session.scalar(
            select(OutlineVersion)
            .where(OutlineVersion.project_id == project.id)
            .order_by(OutlineVersion.version.desc())
            .limit(1)
        )
    if version is None:
        return OutlineBundle()
    pages = list(
        (
            await session.scalars(
                select(OutlinePageVersion)
                .where(OutlinePageVersion.outline_version_id == version.id)
                .order_by(OutlinePageVersion.position)
            )
        ).all()
    )
    sections = list(
        (
            await session.scalars(
                select(OutlineSectionVersion)
                .where(OutlineSectionVersion.outline_version_id == version.id)
                .order_by(OutlineSectionVersion.position)
            )
        ).all()
    )
    return OutlineBundle(version=version, pages=pages, sections=sections)


async def load_profile(session: AsyncSession, project: Project) -> RequirementsProfile | None:
    if project.current_profile_version_id:
        row = await session.get(RequirementsProfile, project.current_profile_version_id)
        if row:
            return row
    return await session.scalar(
        select(RequirementsProfile)
        .where(RequirementsProfile.project_id == project.id)
        .order_by(RequirementsProfile.version.desc())
        .limit(1)
    )


async def load_style_selection(session: AsyncSession, project: Project) -> tuple[StyleSelection | None, StyleDefinition | None]:
    selection: StyleSelection | None = None
    if project.current_style_selection_id:
        selection = await session.get(StyleSelection, project.current_style_selection_id)
    if selection is None:
        selection = await session.scalar(
            select(StyleSelection)
            .where(StyleSelection.project_id == project.id)
            .order_by(StyleSelection.created_at.desc())
            .limit(1)
        )
    if selection is None:
        return None, None
    definition = await session.get(StyleDefinition, selection.style_definition_id)
    return selection, definition


async def compute_profile_dirty(session: AsyncSession, project: Project, profile: RequirementsProfile | None = None) -> bool:
    profile = profile or await load_profile(session, project)
    if profile is None:
        return False
    questions = list(
        (
            await session.scalars(
                select(InterviewQuestion).where(InterviewQuestion.project_id == project.id).order_by("position")
            )
        ).all()
    )
    answers: dict[str, str] = {}
    for q in questions:
        ans = await session.scalar(select(InterviewAnswer).where(InterviewAnswer.question_id == q.id))
        if ans:
            answers[q.question_key] = ans.option_key
    materials = list(
        (
            await session.scalars(
                select(Material).where(Material.project_id == project.id, Material.status != "REMOVED")
            )
        ).all()
    )
    gap_rows = (
        await session.execute(
            select(GapSuggestion.id, GapDecision.selected)
            .join(GapDecision, GapDecision.gap_suggestion_id == GapSuggestion.id)
            .where(GapSuggestion.project_id == project.id)
        )
    ).all()
    selected = [str(gid) for gid, sel in gap_rows if sel]
    web_skipped = bool(profile.web_skipped)
    sources = list(
        (
            await session.scalars(select(SourceItem.id).where(SourceItem.project_id == project.id))
        ).all()
    )
    expected = profile_fingerprint(
        answers=answers,
        material_ids=[str(m.id) for m in materials],
        gap_selected_ids=selected,
        web_skipped=web_skipped,
        source_ids=[str(s) for s in sources],
    )
    return expected != profile.input_fingerprint


@dataclass
class PageArtifacts:
    pointers: dict[tuple[UUID, str], ArtifactPointer] = field(default_factory=dict)
    versions: dict[UUID, ArtifactVersion] = field(default_factory=dict)
    history_depth: dict[tuple[UUID, str], int] = field(default_factory=dict)


async def load_page_artifacts(session: AsyncSession, project: Project) -> PageArtifacts:
    pointers = list(
        (await session.scalars(select(ArtifactPointer).where(ArtifactPointer.project_id == project.id))).all()
    )
    version_ids = [p.artifact_version_id for p in pointers]
    versions: dict[UUID, ArtifactVersion] = {}
    if version_ids:
        rows = (await session.scalars(select(ArtifactVersion).where(ArtifactVersion.id.in_(version_ids)))).all()
        versions = {v.id: v for v in rows}
    depth_rows = (
        await session.execute(
            select(PageHistoryEntry.page_id, PageHistoryEntry.kind, func.count())
            .where(PageHistoryEntry.project_id == project.id, PageHistoryEntry.popped_at.is_(None))
            .group_by(PageHistoryEntry.page_id, PageHistoryEntry.kind)
        )
    ).all()
    depths = {(pid, kind): int(count) for pid, kind, count in depth_rows}
    return PageArtifacts(
        pointers={(p.page_id, p.kind): p for p in pointers},
        versions=versions,
        history_depth=depths,
    )


async def load_recent_jobs(session: AsyncSession, project: Project, limit: int = 400) -> list[Job]:
    return list(
        (
            await session.scalars(
                select(Job).where(Job.project_id == project.id).order_by(Job.created_at.desc()).limit(limit)
            )
        ).all()
    )


def _job_page_id(job: Job) -> UUID | None:
    raw = (job.payload or {}).get("pageId")
    try:
        return UUID(str(raw)) if raw else None
    except ValueError:
        return None


def _job_kind(job: Job) -> str | None:
    if job.type == "PLAN_PAGE":
        return "PLAN"
    if job.type == "DESIGN_PAGE":
        return "DESIGN"
    return None


def _current_chrome(page: OutlinePageVersion, bundle: OutlineBundle) -> tuple[str, str | None]:
    section_label = bundle.section_titles.get(page.section_key)
    return (
        chrome_version(
            page_id=str(page.page_id),
            title=page.title,
            position=page.position,
            deck_order=page.position,
            section_key=page.section_key,
            section_label=section_label,
        ),
        section_label,
    )


def derive_page_states(
    *,
    project: Project,
    bundle: OutlineBundle,
    artifacts: PageArtifacts,
    jobs: list[Job],
    style: StyleSelection | None,
    style_def: StyleDefinition | None,
) -> dict[UUID, dict[str, Any]]:
    active_by_page: dict[tuple[UUID, str], Job] = {}
    failed_by_page: dict[tuple[UUID, str], Job] = {}
    for job in jobs:
        pid = _job_page_id(job)
        kind = _job_kind(job)
        if not pid or not kind:
            continue
        payload_epoch = int((job.payload or {}).get("epoch", project.epoch))
        if payload_epoch != project.epoch:
            continue
        if job.state in (JobState.QUEUED.value, JobState.RUNNING.value):
            active_by_page[(pid, kind)] = job
        elif job.state == JobState.FAILED.value:
            current = failed_by_page.get((pid, kind))
            if current is None or (job.completed_at or job.updated_at) > (current.completed_at or current.updated_at):
                failed_by_page[(pid, kind)] = job

    states: dict[UUID, dict[str, Any]] = {}
    for page in bundle.pages:
        section_label = bundle.section_titles.get(page.section_key)
        chrome_v, _ = _current_chrome(page, bundle)
        plan_pointer = artifacts.pointers.get((page.page_id, "PLAN"))
        plan_version = artifacts.versions.get(plan_pointer.artifact_version_id) if plan_pointer else None
        expected_plan_fp = plan_fingerprint(
            project_id=str(project.id),
            page_id=str(page.page_id),
            page_type=page.page_type,
            section_key=page.section_key,
            key_points=list(page.key_points or []),
        )
        plan_status = PageStatus.PENDING
        failed_plan = failed_by_page.get((page.page_id, "PLAN"))
        plan_failed_recent = bool(
            failed_plan
            and (
                plan_pointer is None
                or (failed_plan.completed_at or failed_plan.updated_at) > plan_pointer.updated_at
            )
        )
        if (page.page_id, "PLAN") in active_by_page:
            plan_status = PageStatus.PLANNING
        elif plan_failed_recent:
            plan_status = PageStatus.ERROR
        elif plan_version is not None:
            plan_status = PageStatus.DONE if plan_version.input_fingerprint == expected_plan_fp else PageStatus.STALE

        design_pointer = artifacts.pointers.get((page.page_id, "DESIGN"))
        design_version = artifacts.versions.get(design_pointer.artifact_version_id) if design_pointer else None
        expected_design_fp = None
        if plan_version and style and style_def:
            expected_design_fp = design_fingerprint(
                project_id=str(project.id),
                page_id=str(page.page_id),
                plan_artifact_version_id=str(plan_version.id),
                style_definition_id=str(style_def.id),
                style_version=style.style_version,
            )
        design_status = PageStatus.PENDING
        failed_design = failed_by_page.get((page.page_id, "DESIGN"))
        design_failed_recent = bool(
            failed_design
            and (
                design_pointer is None
                or (failed_design.completed_at or failed_design.updated_at) > design_pointer.updated_at
            )
        )
        if (page.page_id, "DESIGN") in active_by_page:
            design_status = PageStatus.DESIGNING
        elif design_failed_recent:
            design_status = PageStatus.ERROR
        elif design_version is not None:
            stored_chrome = (design_version.upstream_refs or {}).get("chromeVersion")
            if expected_design_fp and design_version.input_fingerprint != expected_design_fp:
                design_status = PageStatus.STALE
            elif stored_chrome and stored_chrome != chrome_v:
                design_status = PageStatus.STALE
            else:
                design_status = PageStatus.DONE

        states[page.page_id] = {
            "page": page,
            "sectionLabel": section_label,
            "chromeVersion": chrome_v,
            "expectedPlanFingerprint": expected_plan_fp,
            "expectedDesignFingerprint": expected_design_fp,
            "plan": ArtifactStatus(
                status=plan_status.value,
                artifact_version_id=plan_version.id if plan_version else None,
                version=plan_version.version if plan_version else None,
                can_undo=artifacts.history_depth.get((page.page_id, "PLAN"), 0) > 0,
                history_depth=artifacts.history_depth.get((page.page_id, "PLAN"), 0),
                error=None,
            ),
            "design": ArtifactStatus(
                status=design_status.value,
                artifact_version_id=design_version.id if design_version else None,
                version=design_version.version if design_version else None,
                can_undo=artifacts.history_depth.get((page.page_id, "DESIGN"), 0) > 0,
                history_depth=artifacts.history_depth.get((page.page_id, "DESIGN"), 0),
                error=None,
            ),
            "activeJob": None,
        }
        active = active_by_page.get((page.page_id, "PLAN")) or active_by_page.get((page.page_id, "DESIGN"))
        if active:
            states[page.page_id]["activeJob"] = ActiveJobRef(
                job_id=active.id, type=active.type, state=active.state, page_id=page.page_id
            )
    return states


async def build_page_list(session: AsyncSession, project: Project, user_id: UUID | None = None) -> PageListDTO:
    bundle = await load_outline(session, project)
    artifacts = await load_page_artifacts(session, project)
    jobs = await load_recent_jobs(session, project)
    style, style_def = await load_style_selection(session, project)
    states = derive_page_states(
        project=project, bundle=bundle, artifacts=artifacts, jobs=jobs, style=style, style_def=style_def
    )
    counts = PageCountsDTO(total=len(bundle.pages))
    pages: list[PageSummaryDTO] = []
    for page in bundle.pages:
        state = states[page.page_id]
        p = state["plan"]
        d = state["design"]
        counts.plan_done += p.status == PageStatus.DONE.value
        counts.plan_pending += p.status == PageStatus.PENDING.value
        counts.plan_running += p.status == PageStatus.PLANNING.value
        counts.plan_stale += p.status == PageStatus.STALE.value
        counts.plan_error += p.status == PageStatus.ERROR.value
        counts.design_done += d.status == PageStatus.DONE.value
        counts.design_pending += d.status == PageStatus.PENDING.value
        counts.design_running += d.status == PageStatus.DESIGNING.value
        counts.design_stale += d.status == PageStatus.STALE.value
        counts.design_error += d.status == PageStatus.ERROR.value
        pages.append(
            PageSummaryDTO(
                page_id=page.page_id,
                position=page.position,
                page_type=page.page_type,
                section_key=page.section_key,
                section_title=state["sectionLabel"] or "",
                title=page.title,
                plan=p,
                design=d,
                active_job=state["activeJob"],
            )
        )
    return PageListDTO(
        outline_version_id=bundle.version.id if bundle.version else None,
        project_version=project.version,
        counts=counts,
        pages=pages,
    )


def compute_stage_states(
    *,
    project: Project,
    profile_exists: bool,
    profile_dirty: bool,
    bundle: OutlineBundle,
    page_states: dict[UUID, dict[str, Any]],
    style_selection: StyleSelection | None,
    active_jobs: list[Job],
) -> list[StageStateDTO]:
    active_types = {j.type for j in active_jobs}
    plan_statuses = [s["plan"].status for s in page_states.values()]
    design_statuses = [s["design"].status for s in page_states.values()]
    plan_complete = bool(bundle.pages) and all(s == PageStatus.DONE.value for s in plan_statuses)
    design_complete = bool(bundle.pages) and all(s == PageStatus.DONE.value for s in design_statuses)
    any_plan = any(s != PageStatus.PENDING.value for s in plan_statuses)
    any_design = any(s != PageStatus.PENDING.value for s in design_statuses)
    plan_error = any(s == PageStatus.ERROR.value for s in plan_statuses)
    design_error = any(s == PageStatus.ERROR.value for s in design_statuses)
    plan_stale = any(s == PageStatus.STALE.value for s in plan_statuses)
    design_stale = any(s == PageStatus.STALE.value for s in design_statuses)

    stage_status: dict[Stage, StageStatus] = {}
    reachable: dict[Stage, bool] = {s: False for s in STAGE_ORDER}
    blockers: dict[Stage, list[StageBlockerDTO]] = {s: [] for s in STAGE_ORDER}
    stale_reasons: dict[Stage, list[str]] = {s: [] for s in STAGE_ORDER}

    reachable[Stage.INTAKE] = True
    stage_status[Stage.INTAKE] = (
        StageStatus.AVAILABLE if project.stage == Stage.INTAKE.value else StageStatus.COMPLETE
    )

    reachable[Stage.RESEARCH] = bool(project.topic.strip())
    if profile_exists and not profile_dirty:
        research_status = StageStatus.COMPLETE
    elif active_types & {"INGEST", "DIGEST", "SEARCH", "GAP_SUGGEST", "PROFILE"} or project.stage == Stage.RESEARCH.value:
        research_status = StageStatus.IN_PROGRESS
    else:
        research_status = StageStatus.AVAILABLE
    stage_status[Stage.RESEARCH] = research_status

    outline_ok = profile_exists and not profile_dirty
    reachable[Stage.OUTLINE] = outline_ok
    if not outline_ok:
        blockers[Stage.OUTLINE].append(
            StageBlockerDTO(
                code="profile_missing" if not profile_exists else "profile_dirty",
                message_key="error.gate.profile_dirty",
                stage=Stage.RESEARCH.value,
            )
        )
    if profile_dirty:
        stale_reasons[Stage.OUTLINE].append("profile_version_changed")
        stage_status[Stage.OUTLINE] = StageStatus.STALE
    elif bundle.version and bundle.confirmed:
        stage_status[Stage.OUTLINE] = StageStatus.COMPLETE
    elif "OUTLINE" in active_types:
        stage_status[Stage.OUTLINE] = StageStatus.IN_PROGRESS
    elif bundle.version:
        stage_status[Stage.OUTLINE] = StageStatus.STALE
        stale_reasons[Stage.OUTLINE].append("outline_unconfirmed")
    else:
        stage_status[Stage.OUTLINE] = StageStatus.AVAILABLE if outline_ok else StageStatus.LOCKED

    plan_ok = bool(bundle.version) and bundle.confirmed
    reachable[Stage.PLAN] = plan_ok
    if not bundle.version:
        blockers[Stage.PLAN].append(
            StageBlockerDTO(code="outline_missing", message_key="error.gate.outline_missing", stage=Stage.OUTLINE.value)
        )
    elif not bundle.confirmed:
        blockers[Stage.PLAN].append(
            StageBlockerDTO(
                code="outline_unconfirmed",
                message_key="error.gate.outline_unconfirmed",
                stage=Stage.OUTLINE.value,
            )
        )
    if plan_error:
        stage_status[Stage.PLAN] = StageStatus.ERROR
    elif plan_complete:
        stage_status[Stage.PLAN] = StageStatus.COMPLETE
    elif {"PLAN_PAGE"} & active_types:
        stage_status[Stage.PLAN] = StageStatus.IN_PROGRESS
    elif plan_stale or any_plan:
        stage_status[Stage.PLAN] = StageStatus.STALE if plan_stale else StageStatus.IN_PROGRESS
    else:
        stage_status[Stage.PLAN] = StageStatus.AVAILABLE if plan_ok else StageStatus.LOCKED
    if plan_stale:
        stale_reasons[Stage.PLAN].append("plan_inputs_changed")

    style_ok = plan_complete
    reachable[Stage.STYLE] = style_ok
    if not plan_complete:
        blockers[Stage.STYLE].append(
            StageBlockerDTO(
                code="plan_incomplete", message_key="error.gate.plan_incomplete", stage=Stage.PLAN.value
            )
        )
    if style_selection and style_selection.confirmed_at:
        stage_status[Stage.STYLE] = StageStatus.COMPLETE
    elif style_selection:
        stage_status[Stage.STYLE] = StageStatus.IN_PROGRESS
    else:
        stage_status[Stage.STYLE] = StageStatus.AVAILABLE if style_ok else StageStatus.LOCKED

    reachable[Stage.DESIGN] = bool(style_selection and style_selection.confirmed_at)
    if style_selection is None:
        blockers[Stage.DESIGN].append(
            StageBlockerDTO(
                code="style_not_selected",
                message_key="error.gate.style_not_selected",
                stage=Stage.STYLE.value,
            )
        )
    elif not style_selection.confirmed_at:
        blockers[Stage.DESIGN].append(
            StageBlockerDTO(
                code="style_unconfirmed",
                message_key="error.gate.style_unconfirmed",
                stage=Stage.STYLE.value,
            )
        )
    if design_error:
        stage_status[Stage.DESIGN] = StageStatus.ERROR
    elif design_complete:
        stage_status[Stage.DESIGN] = StageStatus.COMPLETE
    elif {"DESIGN_PAGE"} & active_types:
        stage_status[Stage.DESIGN] = StageStatus.IN_PROGRESS
    elif design_stale or any_design:
        stage_status[Stage.DESIGN] = StageStatus.STALE if design_stale else StageStatus.IN_PROGRESS
    else:
        stage_status[Stage.DESIGN] = StageStatus.AVAILABLE if reachable[Stage.DESIGN] else StageStatus.LOCKED
    if design_stale:
        stale_reasons[Stage.DESIGN].append("design_inputs_changed")

    result: list[StageStateDTO] = []
    for stage in STAGE_ORDER:
        token = None
        expires = None
        if (
            project.mode == ProjectMode.FULLY_AUTOMATIC.value
            and stage == project.stage
            and stage in (Stage.OUTLINE, Stage.PLAN)
            and stage_status[stage] not in (StageStatus.LOCKED, StageStatus.IN_PROGRESS, StageStatus.ERROR)
        ):
            token, exp = issue_advance_token(
                project_id=project.id, from_stage=stage.value, stage_version=project.version
            )
            from datetime import UTC, datetime

            expires = datetime.fromtimestamp(exp, tz=UTC)
        result.append(
            StageStateDTO(
                stage=stage.value,
                status=stage_status[stage].value,
                reachable=reachable[stage],
                stale_reasons=stale_reasons[stage],
                blockers=blockers[stage],
                advance_token=token,
                advance_token_expires_at=expires,
            )
        )
    return result


async def build_snapshot(session: AsyncSession, project: Project) -> ProjectSnapshotDTO:
    settings = get_settings()
    profile = await load_profile(session, project)
    dirty = await compute_profile_dirty(session, project, profile)
    bundle = await load_outline(session, project)
    artifacts = await load_page_artifacts(session, project)
    jobs = await load_recent_jobs(session, project)
    style, style_def = await load_style_selection(session, project)
    page_states = derive_page_states(
        project=project, bundle=bundle, artifacts=artifacts, jobs=jobs, style=style, style_def=style_def
    )
    active_jobs = [
        ActiveJobRef(
            job_id=j.id,
            type=j.type,
            state=j.state,
            page_id=_job_page_id(j),
        )
        for j in jobs
        if j.state in (JobState.QUEUED.value, JobState.RUNNING.value)
    ]
    material_count = int(
        await session.scalar(
            select(func.count()).select_from(Material).where(
                Material.project_id == project.id, Material.status != "REMOVED"
            )
        )
        or 0
    )
    web_count = int(
        await session.scalar(
            select(func.count()).select_from(SourceItem).where(
                SourceItem.project_id == project.id, SourceItem.origin == "WEB"
            )
        )
        or 0
    )
    from app.models import ExportJob

    latest_export_row = await session.scalar(
        select(ExportJob).where(ExportJob.project_id == project.id).order_by(ExportJob.created_at.desc()).limit(1)
    )
    sequence = await session.scalar(
        select(ProjectEventCounter.last_sequence).where(ProjectEventCounter.project_id == project.id)
    ) or 0
    statuses = [s["plan"].status for s in page_states.values()]
    dstatuses = [s["design"].status for s in page_states.values()]
    counts = SnapshotCountsDTO(
        materials=material_count,
        web_sources=web_count,
        pages=len(bundle.pages),
        sections=len(bundle.sections),
        plan_done=sum(1 for s in statuses if s == PageStatus.DONE.value),
        plan_total=len(statuses),
        design_done=sum(1 for s in dstatuses if s == PageStatus.DONE.value),
        design_total=len(dstatuses),
        stale_pages=sum(1 for s in statuses + dstatuses if s == PageStatus.STALE.value),
        error_pages=sum(1 for s in statuses + dstatuses if s == PageStatus.ERROR.value),
    )
    stages = compute_stage_states(
        project=project,
        profile_exists=profile is not None,
        profile_dirty=dirty,
        bundle=bundle,
        page_states=page_states,
        style_selection=style,
        active_jobs=[j for j in jobs if j.state in (JobState.QUEUED.value, JobState.RUNNING.value)],
    )
    snapshot = ProjectSnapshotDTO(
        project=ProjectDTO(
            id=project.id,
            name=project.name,
            topic=project.topic,
            mode=project.mode,
            status=project.status,
            stage=project.stage,
            version=project.version,
            epoch=project.epoch,
            created_at=project.created_at,
            updated_at=project.updated_at,
        ),
        stages=stages,
        pointers={
            "profileVersionId": profile.id if profile else None,
            "outlineVersionId": bundle.version.id if bundle.version else None,
            "styleSelectionId": style.id if style else None,
        },
        counts=counts,
        profile_dirty=dirty,
        material_limit=settings.material_max_count,
        style_selection=(
            {
                "styleKey": style_def.key if style_def else "unknown",
                "styleVersion": style.style_version,
                "confirmed": bool(style.confirmed_at),
                "confirmedAt": style.confirmed_at,
            }
            if style
            else None
        ),
        active_jobs=active_jobs,
        latest_export_id=latest_export_row.id if latest_export_row else None,
        sequence=int(sequence),
        server_time=utcnow(),
    )
    return snapshot


def make_stale_summary(
    project: Project,
    cause: str,
    *,
    plan_pages: list[UUID] | None = None,
    design_pages: list[UUID] | None = None,
    changed_pages: int | None = None,
) -> StaleSummaryDTO:
    plan_pages = plan_pages or []
    design_pages = design_pages or []
    rerun_plan = len(plan_pages)
    rerun_design = len(design_pages)
    denominator = changed_pages if changed_pages is not None else max(len(plan_pages), len(design_pages))
    cascade = (rerun_plan + rerun_design) / denominator if denominator else None
    return StaleSummaryDTO(
        changed=bool(plan_pages or design_pages),
        cause=cause,
        affected={"plan": plan_pages, "design": design_pages},
        rerun={"plan": rerun_plan, "design": rerun_design},
        cascade_ratio=cascade,
        project_version=project.version,
    )
