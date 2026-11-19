from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import gate, not_found, validation
from app.core.idempotency import bump_project
from app.core.ids import new_id, utcnow
from app.domain.enums import (
    JobState,
    JobType,
    ProjectMode,
    ProjectStatus,
    Stage,
    StageStatus,
)
from app.models import (
    ArtifactLineage,
    ArtifactPointer,
    ArtifactSourceRef,
    ArtifactVersion,
    DomainEvent,
    ExportArtifact,
    ExportJob,
    GapDecision,
    GapSuggestion,
    IdempotencyRecord,
    InterviewAnswer,
    InterviewQuestion,
    Job,
    Material,
    MaterialDigest,
    OutlinePageVersion,
    OutlineSectionVersion,
    OutlineVersion,
    Page,
    PageHistoryEntry,
    PolicyRecord,
    Project,
    ProjectEventCounter,
    ProjectSnapshotCache,
    RequirementsProfile,
    SourceItem,
    StyleSelection,
    UsageRecord,
)
from app.schemas.dto import (
    JobDTO,
    JobProgressDTO,
    PageError,
    ProjectDTO,
    ProjectSnapshotDTO,
)
from app.services.events import events
from app.services.jobs import job_page_id
from app.services.state import build_snapshot

JOB_STAGE: dict[str, str] = {
    JobType.INGEST.value: Stage.RESEARCH.value,
    JobType.DIGEST.value: Stage.RESEARCH.value,
    JobType.SEARCH.value: Stage.RESEARCH.value,
    JobType.GAP_SUGGEST.value: Stage.RESEARCH.value,
    JobType.PROFILE.value: Stage.RESEARCH.value,
    JobType.OUTLINE.value: Stage.OUTLINE.value,
    JobType.PLAN_PAGE.value: Stage.PLAN.value,
    JobType.DESIGN_PAGE.value: Stage.DESIGN.value,
    JobType.EXPORT.value: Stage.DESIGN.value,
    JobType.DELETE_PROJECT.value: Stage.INTAKE.value,
}

_ERROR_MESSAGE_KEYS: dict[str, str] = {
    "deadline_exceeded": "error.internal.unexpected",
    "no_handler": "error.internal.unexpected",
    "internal": "error.internal.unexpected",
    "internal_error": "error.internal.unexpected",
    "provider_timeout": "error.provider.timeout",
    "provider_unavailable": "error.provider.unavailable",
    "parse_failure": "error.parse.type_mismatch",
    "validation": "error.validation.invalid_request",
}


def normalize_topic(raw: str) -> str:
    topic = (raw or "").strip()
    if not topic:
        raise validation("error.validation.empty_topic")
    return topic


def validate_mode(mode: str) -> str:
    if mode not in {m.value for m in ProjectMode}:
        raise validation(
            "error.validation.invalid_request",
            {"field": "mode", "allowed": [m.value for m in ProjectMode]},
        )
    return mode


def project_dto(project: Project) -> ProjectDTO:
    return ProjectDTO(
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
    )


def job_stage(job_type: str) -> str:
    return JOB_STAGE.get(job_type, Stage.INTAKE.value)


def job_dto(job: Job, *, started_at: datetime | None = None) -> JobDTO:
    error: PageError | None = None
    if job.last_error_code:
        category = job.last_error_class or "internal"
        error = PageError(
            code=job.last_error_code,
            category=category,
            message_key=_ERROR_MESSAGE_KEYS.get(category)
            or _ERROR_MESSAGE_KEYS.get(job.last_error_code)
            or "error.internal.unexpected",
            retryable=category
            in {"conflict", "rate_limited", "provider_timeout", "provider_unavailable", "internal"},
            page_id=job_page_id(job),
        )
    progress: JobProgressDTO | None = None
    raw_progress = job.progress or {}
    if raw_progress:
        progress = JobProgressDTO(
            phase=str(raw_progress.get("phase", "")),
            current=int(raw_progress.get("current", 0) or 0),
            total=int(raw_progress.get("total", 0) or 0),
        )
    return JobDTO(
        job_id=job.id,
        project_id=job.project_id,
        type=job.type,
        state=job.state,
        stage=job_stage(job.type),
        page_id=job_page_id(job),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        cancel_requested=job.cancel_requested_at is not None,
        queued_at=job.created_at,
        started_at=started_at,
        completed_at=job.completed_at,
        deadline_at=job.deadline_at,
        error=error,
        progress=progress,
    )


async def job_started_at(session: AsyncSession, job_id: UUID) -> datetime | None:
    from app.models import JobAttempt

    return await session.scalar(select(func.min(JobAttempt.started_at)).where(JobAttempt.job_id == job_id))


async def load_job(session: AsyncSession, project_id: UUID, job_id: UUID) -> Job:
    job = await session.scalar(select(Job).where(Job.id == job_id, Job.project_id == project_id))
    if job is None:
        raise not_found("error.not_found.job")
    return job


async def latest_sequence(session: AsyncSession, project_id: UUID) -> int:
    return int(await events.latest_sequence(session, project_id))


# ---- Create / update -------------------------------------------------------


@dataclass
class CreateResult:
    project: Project
    snapshot: ProjectSnapshotDTO
    sequence: int


async def create_project(
    session: AsyncSession,
    *,
    owner_user_id: UUID | None,
    account_id: UUID | None,
    topic: str,
    name: str | None,
    mode: str,
) -> CreateResult:
    normalized_topic = normalize_topic(topic)
    normalized_mode = validate_mode(mode)
    project_name = (name or "").strip() or normalized_topic
    project = Project(
        id=new_id(),
        account_id=account_id,
        owner_user_id=owner_user_id,
        name=project_name,
        topic=normalized_topic,
        mode=normalized_mode,
        status=ProjectStatus.ACTIVE.value,
        stage=Stage.INTAKE.value,
        version=1,
        epoch=1,
        current_profile_version_id=None,
        current_outline_version_id=None,
        current_style_selection_id=None,
    )
    session.add(project)
    await session.flush()
    session.add(ProjectEventCounter(project_id=project.id, last_sequence=0))
    await session.flush()
    event = await events.append(
        session,
        project.id,
        "projectCreated",
        {
            "mode": project.mode,
            "stage": project.stage,
            "projectVersion": project.version,
        },
    )
    await session.flush()
    snapshot = await build_snapshot(session, project)
    return CreateResult(project=project, snapshot=snapshot, sequence=event.sequence)


async def update_project(
    session: AsyncSession,
    project: Project,
    *,
    name: str | None,
    topic: str | None,
) -> Project:
    if name is None and topic is None:
        raise validation("error.validation.invalid_request", {"fields": ["name", "topic"]})
    if topic is not None:
        if project.stage != Stage.INTAKE.value:
            raise gate("error.gate.topic_locked")
        normalized_topic = normalize_topic(topic)
    else:
        normalized_topic = None
    if name is not None:
        cleaned_name = name.strip()
        if not cleaned_name:
            raise validation("error.validation.invalid_request", {"field": "name"})
        project.name = cleaned_name
    if normalized_topic is not None:
        project.topic = normalized_topic
    bump_project(project)
    await session.flush()
    return project


# ---- Job cancellation ------------------------------------------------------


async def cancel_active_jobs(
    session: AsyncSession,
    project: Project,
    *,
    reason: str,
) -> tuple[list[UUID], int | None]:
    """Cancel queued work and request cooperative cancel for running work."""
    active = list(
        (
            await session.scalars(
                select(Job)
                .where(
                    Job.project_id == project.id,
                    Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
                )
                .order_by(Job.created_at)
            )
        ).all()
    )
    cancelled_ids: list[UUID] = []
    last_sequence: int | None = None
    now = utcnow()
    for job in active:
        if job.state == JobState.QUEUED.value:
            job.state = JobState.CANCELLED.value
            job.completed_at = now
            job.active_operation_key = None
            job.lease_owner = None
            job.lease_expires_at = None
            event = await events.append(
                session,
                project.id,
                "jobCancelled",
                {
                    "jobId": str(job.id),
                    "jobType": job.type,
                    "pageId": job_page_id(job),
                    "reason": reason,
                },
            )
            last_sequence = event.sequence
            cancelled_ids.append(job.id)
        else:
            cancelled_ids.append(job.id)
            if job.cancel_requested_at is not None:
                continue
            job.cancel_requested_at = now
            event = await events.append(
                session,
                project.id,
                "jobCancelled",
                {
                    "jobId": str(job.id),
                    "jobType": job.type,
                    "pageId": job_page_id(job),
                    "reason": reason,
                },
            )
            last_sequence = event.sequence
    await session.flush()
    return cancelled_ids, last_sequence


async def cancel_job(session: AsyncSession, project: Project, job: Job) -> tuple[bool, int | None]:
    """Apply one cancellation intent. Returns (changed, lastSequence)."""
    if job.state == JobState.QUEUED.value:
        job.state = JobState.CANCELLED.value
        job.completed_at = utcnow()
        job.active_operation_key = None
        job.lease_owner = None
        job.lease_expires_at = None
        event = await events.append(
            session,
            project.id,
            "jobCancelled",
            {
                "jobId": str(job.id),
                "jobType": job.type,
                "pageId": job_page_id(job),
                "reason": "user_cancelled",
            },
        )
        bump_project(project)
        await session.flush()
        return True, event.sequence
    if job.state == JobState.RUNNING.value and job.cancel_requested_at is None:
        job.cancel_requested_at = utcnow()
        event = await events.append(
            session,
            project.id,
            "jobCancelled",
            {
                "jobId": str(job.id),
                "jobType": job.type,
                "pageId": job_page_id(job),
                "reason": "user_cancelled",
            },
        )
        bump_project(project)
        await session.flush()
        return True, event.sequence
    return False, None


# ---- Restart ---------------------------------------------------------------


@dataclass
class RestartScope:
    page_ids: list[UUID]
    plan_page_ids: list[UUID]
    design_page_ids: list[UUID]


async def clear_derived_state(session: AsyncSession, project: Project) -> RestartScope:
    """Remove research/outline/plan/design/export state but keep materials and history log."""
    history_page_ids = list(
        (
            await session.scalars(
                select(Page.id).where(Page.project_id == project.id, Page.retired_at.is_(None))
            )
        ).all()
    )
    pointers = list(
        (await session.scalars(select(ArtifactPointer).where(ArtifactPointer.project_id == project.id))).all()
    )
    scope = RestartScope(
        page_ids=history_page_ids,
        plan_page_ids=[p.page_id for p in pointers if p.kind == "PLAN"],
        design_page_ids=[p.page_id for p in pointers if p.kind == "DESIGN"],
    )

    outline_ids = select(OutlineVersion.id).where(OutlineVersion.project_id == project.id)

    # Artifact chain first: refs, lineage, history, pointers, versions.
    await session.execute(delete(ArtifactSourceRef).where(ArtifactSourceRef.project_id == project.id))
    await session.execute(delete(ArtifactLineage).where(ArtifactLineage.project_id == project.id))
    await session.execute(delete(ArtifactPointer).where(ArtifactPointer.project_id == project.id))
    await session.execute(delete(PageHistoryEntry).where(PageHistoryEntry.project_id == project.id))
    await session.execute(delete(ArtifactVersion).where(ArtifactVersion.project_id == project.id))

    # Exports.
    await session.execute(delete(ExportArtifact).where(ExportArtifact.project_id == project.id))
    await session.execute(delete(ExportJob).where(ExportJob.project_id == project.id))

    # Style / profile / interview / gaps.
    await session.execute(delete(StyleSelection).where(StyleSelection.project_id == project.id))
    await session.execute(delete(RequirementsProfile).where(RequirementsProfile.project_id == project.id))
    await session.execute(delete(InterviewAnswer).where(InterviewAnswer.project_id == project.id))
    await session.execute(delete(InterviewQuestion).where(InterviewQuestion.project_id == project.id))
    await session.execute(delete(GapDecision).where(GapDecision.project_id == project.id))
    await session.execute(delete(GapSuggestion).where(GapSuggestion.project_id == project.id))

    # Outline versions and their child rows.
    await session.execute(
        delete(OutlinePageVersion).where(OutlinePageVersion.outline_version_id.in_(outline_ids))
    )
    await session.execute(
        delete(OutlineSectionVersion).where(OutlineSectionVersion.outline_version_id.in_(outline_ids))
    )
    await session.execute(delete(OutlineVersion).where(OutlineVersion.project_id == project.id))

    # Web sources are re-researched; provided sources belong to retained materials.
    await session.execute(
        delete(SourceItem).where(SourceItem.project_id == project.id, SourceItem.origin == "WEB")
    )
    await session.execute(delete(ProjectSnapshotCache).where(ProjectSnapshotCache.project_id == project.id))

    # Page identities are never reused; retire them for audit.
    await session.execute(
        update(Page)
        .where(Page.project_id == project.id, Page.retired_at.is_(None))
        .values(retired_at=utcnow())
    )
    await session.flush()
    return scope


@dataclass
class RestartResult:
    project: Project
    snapshot: ProjectSnapshotDTO
    cancelled_job_ids: list[UUID]
    sequence: int


async def restart_project(session: AsyncSession, project: Project) -> RestartResult:
    previous_stage = project.stage
    scope = await clear_derived_state(session, project)
    cancelled_ids, _ = await cancel_active_jobs(session, project, reason="project_restart")

    project.stage = Stage.INTAKE.value
    project.epoch += 1
    project.current_profile_version_id = None
    project.current_outline_version_id = None
    project.current_style_selection_id = None
    bump_project(project)
    await session.flush()

    previous_status = (
        StageStatus.AVAILABLE.value if previous_stage == Stage.INTAKE.value else StageStatus.IN_PROGRESS.value
    )
    await events.append(
        session,
        project.id,
        "stageStateChanged",
        {
            "stage": Stage.INTAKE.value,
            "status": StageStatus.AVAILABLE.value,
            "previousStatus": previous_status,
            "reachable": True,
            "staleReasons": [],
            "projectVersion": project.version,
        },
    )
    stale_event = await events.append(
        session,
        project.id,
        "staleChanged",
        {
            "fromStage": previous_stage,
            "cause": "RESTART",
            "affectedPageIds": [str(pid) for pid in scope.page_ids],
            "affectedPages": {
                "plan": len(scope.plan_page_ids),
                "design": len(scope.design_page_ids),
            },
            "rerunPages": {"plan": 0, "design": 0},
            "cascadeRatio": None,
            "projectVersion": project.version,
        },
    )
    await session.flush()
    snapshot = await build_snapshot(session, project)
    return RestartResult(
        project=project,
        snapshot=snapshot,
        cancelled_job_ids=cancelled_ids,
        sequence=stale_event.sequence,
    )


# ---- Delete ----------------------------------------------------------------


@dataclass
class DeleteResult:
    project: Project
    job: Job
    sequence: int | None


async def begin_deletion(session: AsyncSession, project: Project) -> DeleteResult:
    project.status = ProjectStatus.DELETING.value
    cancelled_ids, last_sequence = await cancel_active_jobs(session, project, reason="project_deleted")
    from app.services.jobs import enqueue_job

    job = await enqueue_job(
        session,
        project,
        JobType.DELETE_PROJECT,
        operation_key=f"delete:{project.id}",
        active_operation_key=f"delete:{project.id}",
        payload={},
    )
    bump_project(project)
    await session.flush()
    sequence = await latest_sequence(session, project.id)
    return DeleteResult(project=project, job=job, sequence=sequence or last_sequence)


async def _collect_storage_keys(session: AsyncSession, project_id: UUID) -> list[str]:
    keys: list[str] = []
    material_rows = (
        await session.execute(
            select(Material.content_ref, Material.raw_ref).where(Material.project_id == project_id)
        )
    ).all()
    for content_ref, raw_ref in material_rows:
        keys.extend([k for k in (content_ref, raw_ref) if k])
    digest_refs = (
        await session.scalars(select(MaterialDigest.digest_ref).where(MaterialDigest.project_id == project_id))
    ).all()
    keys.extend([k for k in digest_refs if k])
    source_refs = (
        await session.scalars(select(SourceItem.content_ref).where(SourceItem.project_id == project_id))
    ).all()
    keys.extend([k for k in source_refs if k])
    artifact_refs = (
        await session.scalars(
            select(ArtifactVersion.content_ref).where(ArtifactVersion.project_id == project_id)
        )
    ).all()
    keys.extend([k for k in artifact_refs if k])
    export_refs = (
        await session.scalars(select(ExportArtifact.object_key).where(ExportArtifact.project_id == project_id))
    ).all()
    keys.extend([k for k in export_refs if k])
    instruction_refs = (
        await session.scalars(select(Job.instruction_ref).where(Job.project_id == project_id))
    ).all()
    keys.extend([k for k in instruction_refs if k])
    return list(dict.fromkeys(keys))


async def _best_effort_delete(object_store: Any, key: str) -> None:
    try:
        deleter = getattr(object_store, "delete", None)
        if callable(deleter):
            result = deleter(key)
            if inspect.isawaitable(result):
                await result
            return
        client = getattr(object_store, "client", None)
        bucket = getattr(object_store, "bucket", None)
        if client is not None and bucket:
            await asyncio.to_thread(client.delete_object, Bucket=bucket, Key=key)
    except Exception:  # noqa: BLE001 - best effort object cleanup
        return


async def purge_project(session: AsyncSession, project: Project, object_store: Any) -> None:
    """Delete object content and derived rows, then write a scrubbed tombstone."""
    if project.status == ProjectStatus.DELETED.value:
        return
    for key in await _collect_storage_keys(session, project.id):
        await _best_effort_delete(object_store, key)

    outline_ids = select(OutlineVersion.id).where(OutlineVersion.project_id == project.id)

    await session.execute(delete(ArtifactSourceRef).where(ArtifactSourceRef.project_id == project.id))
    await session.execute(delete(ArtifactLineage).where(ArtifactLineage.project_id == project.id))
    await session.execute(delete(ArtifactPointer).where(ArtifactPointer.project_id == project.id))
    await session.execute(delete(PageHistoryEntry).where(PageHistoryEntry.project_id == project.id))
    await session.execute(delete(ArtifactVersion).where(ArtifactVersion.project_id == project.id))
    await session.execute(delete(ExportArtifact).where(ExportArtifact.project_id == project.id))
    await session.execute(delete(ExportJob).where(ExportJob.project_id == project.id))
    await session.execute(delete(StyleSelection).where(StyleSelection.project_id == project.id))
    await session.execute(delete(RequirementsProfile).where(RequirementsProfile.project_id == project.id))
    await session.execute(delete(InterviewAnswer).where(InterviewAnswer.project_id == project.id))
    await session.execute(delete(InterviewQuestion).where(InterviewQuestion.project_id == project.id))
    await session.execute(delete(GapDecision).where(GapDecision.project_id == project.id))
    await session.execute(delete(GapSuggestion).where(GapSuggestion.project_id == project.id))
    await session.execute(
        delete(OutlinePageVersion).where(OutlinePageVersion.outline_version_id.in_(outline_ids))
    )
    await session.execute(
        delete(OutlineSectionVersion).where(OutlineSectionVersion.outline_version_id.in_(outline_ids))
    )
    await session.execute(delete(OutlineVersion).where(OutlineVersion.project_id == project.id))
    await session.execute(delete(SourceItem).where(SourceItem.project_id == project.id))
    await session.execute(delete(MaterialDigest).where(MaterialDigest.project_id == project.id))
    await session.execute(delete(Material).where(Material.project_id == project.id))
    await session.execute(delete(Page).where(Page.project_id == project.id))
    await session.execute(delete(ProjectSnapshotCache).where(ProjectSnapshotCache.project_id == project.id))
    await session.execute(delete(PolicyRecord).where(PolicyRecord.project_id == project.id))
    await session.execute(delete(IdempotencyRecord).where(IdempotencyRecord.project_id == project.id))
    await session.execute(delete(DomainEvent).where(DomainEvent.project_id == project.id))
    await session.execute(delete(ProjectEventCounter).where(ProjectEventCounter.project_id == project.id))
    await session.execute(
        update(UsageRecord).where(UsageRecord.project_id == project.id).values(project_id=None)
    )

    project.status = ProjectStatus.DELETED.value
    project.deleted_at = utcnow()
    project.purge_after = utcnow()
    project.name = ""
    project.topic = ""
    project.current_profile_version_id = None
    project.current_outline_version_id = None
    project.current_style_selection_id = None
    await session.flush()
