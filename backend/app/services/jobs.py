from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ids import new_id, utcnow
from app.domain.enums import JobState, JobType
from app.models import Job, Project
from app.services.events import events


async def find_active(session: AsyncSession, active_operation_key: str) -> Job | None:
    return await session.scalar(
        select(Job).where(
            Job.active_operation_key == active_operation_key,
            Job.state.in_([JobState.QUEUED.value, JobState.RUNNING.value]),
        )
    )


async def enqueue_job(
    session: AsyncSession,
    project: Project,
    job_type: JobType | str,
    *,
    operation_key: str,
    payload: dict[str, Any] | None = None,
    active_operation_key: str | None = None,
    priority: int = 0,
    deadline_seconds: int | None = None,
) -> Job:
    """Insert a durable job row and its jobQueued event in the caller's transaction.

    Callers MUST commit before calling `runner.wake(job.id)`.
    """
    settings = get_settings()
    if active_operation_key:
        existing = await find_active(session, active_operation_key)
        if existing is not None:
            return existing
    now = utcnow()
    seconds = deadline_seconds or settings.job_deadline_seconds
    job = Job(
        id=new_id(),
        project_id=project.id,
        type=str(job_type),
        operation_key=operation_key,
        active_operation_key=active_operation_key,
        state=JobState.QUEUED.value,
        priority=priority,
        payload={
            **(payload or {}),
            "epoch": project.epoch,
            "projectVersion": project.version,
        },
        deadline_at=now + timedelta(seconds=seconds),
        attempt_count=0,
        max_attempts=settings.job_max_attempts,
        fencing_token=0,
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    await session.flush()
    await events.append(
        session,
        project.id,
        "jobQueued",
        {
            "jobId": str(job.id),
            "jobType": job.type,
            "pageId": job.payload.get("pageId"),
            "waitMs": 0,
        },
    )
    return job


def wake_jobs(*jobs: Job) -> None:
    from app.worker.runner import runner

    for job in jobs:
        runner.wake(job.id)


def job_page_id(job: Job) -> UUID | None:
    raw = (job.payload or {}).get("pageId")
    try:
        return UUID(str(raw)) if raw else None
    except (ValueError, TypeError):
        return None
