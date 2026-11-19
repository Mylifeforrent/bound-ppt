from __future__ import annotations

import asyncio
import contextlib
import random
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import SessionFactory
from app.core.errors import AppError
from app.core.ids import new_id, utcnow
from app.domain.enums import JobState, JobType
from app.ingest.search import search
from app.llm.gateway import ModelGateway, gateway
from app.models import Job, JobAttempt
from app.services.events import bus, events
from app.storage import storage


class JobFailure(Exception):
    def __init__(
        self,
        code: str,
        *,
        category: str = "internal",
        message_key: str = "error.internal.unexpected",
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.category = category
        self.message_key = message_key
        self.retryable = retryable


class JobCancelled(Exception):
    pass


@dataclass
class JobContext:
    session: AsyncSession
    job: Job
    attempt_id: UUID
    fencing_token: int
    settings: Settings
    gateway: ModelGateway
    search: Any
    storage: Any
    worker_id: str

    @property
    def project_id(self) -> UUID:
        return self.job.project_id

    @property
    def payload(self) -> dict[str, Any]:
        return dict(self.job.payload or {})

    async def check_cancel(self) -> None:
        value = await self.session.scalar(select(Job.cancel_requested_at).where(Job.id == self.job.id))
        if value is not None:
            raise JobCancelled("cancel_requested")

    async def report_progress(self, phase: str, current: int, total: int) -> None:
        self.job.progress = {"phase": phase, "current": current, "total": total}
        await self.session.flush()

    async def emit_ephemeral(self, payload: dict[str, Any]) -> None:
        bus.publish_ephemeral(self.project_id, payload)

    async def usage(
        self,
        *,
        capability: str,
        unit_type: str,
        quantity: float,
        provider: str,
        estimated_cost: float = 0.0,
        stage: str | None = None,
        page_id: UUID | None = None,
    ) -> None:
        from app.models import UsageRecord

        unique_key = f"{self.job.operation_key}:{unit_type}"
        existing = await self.session.scalar(select(UsageRecord.id).where(UsageRecord.unique_key == unique_key))
        if existing:
            return
        self.session.add(
            UsageRecord(
                id=new_id(),
                unique_key=unique_key,
                operation_key=self.job.operation_key,
                project_id=self.project_id,
                stage=stage or self.job.type,
                page_id=page_id,
                job_id=self.job.id,
                attempt_id=self.attempt_id,
                provider=provider,
                capability=capability,
                unit_type=unit_type,
                quantity=quantity,
                estimated_cost=estimated_cost,
                currency="USD",
                occurred_at=utcnow(),
            )
        )


Handler = Callable[[JobContext], Awaitable[None]]
HANDLERS: dict[str, Handler] = {}


def register(job_type: JobType | str):
    def decorator(fn: Handler) -> Handler:
        HANDLERS[str(job_type)] = fn
        return fn

    return decorator


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class JobRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._queue: asyncio.Queue[UUID] = asyncio.Queue(maxsize=2048)
        self._queued: set[UUID] = set()
        self._tasks: list[asyncio.Task[Any]] = []
        self._stopping = asyncio.Event()
        self._started = False
        self._worker_id = f"worker-{uuid4().hex[:8]}"
        self._generation = asyncio.Semaphore(self.settings.generation_workers)
        self._ingestion = asyncio.Semaphore(self.settings.ingestion_workers)
        self._export = asyncio.Semaphore(self.settings.export_workers)
        self._project_slots: dict[UUID, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(2))
        self._background: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        total = self.settings.generation_workers + self.settings.ingestion_workers + self.settings.export_workers
        self._tasks = [asyncio.create_task(self._worker(i), name=f"job-worker-{i}") for i in range(total)]
        self._tasks.append(asyncio.create_task(self._reconcile_loop(), name="job-reconciler"))
        await self.reconcile_once()

    def wake(self, job_id: UUID) -> None:
        if job_id in self._queued:
            return
        self._queued.add(job_id)
        try:
            self._queue.put_nowait(job_id)
        except asyncio.QueueFull:
            self._queued.discard(job_id)

    def wake_later(self, job_id: UUID, delay: float) -> None:
        task = asyncio.create_task(self._delayed_wake(job_id, delay))
        self._background.add(task)
        task.add_done_callback(self._background.discard)

    async def _delayed_wake(self, job_id: UUID, delay: float) -> None:
        await asyncio.sleep(delay)
        self.wake(job_id)

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        for task in self._background:
            task.cancel()
        await asyncio.gather(*self._tasks, *self._background, return_exceptions=True)
        self._started = False

    async def _worker(self, index: int) -> None:
        while not self._stopping.is_set():
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            self._queued.discard(job_id)
            try:
                await self._run_job(job_id)
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                # The job row carries the durable failure state.
                continue

    async def _semaphore_for(self, job_type: str) -> asyncio.Semaphore:
        if job_type in {JobType.INGEST.value, JobType.DIGEST.value, JobType.SEARCH.value}:
            return self._ingestion
        if job_type == JobType.EXPORT.value:
            return self._export
        return self._generation

    async def _run_job(self, job_id: UUID) -> None:
        # Claim atomically. A zero-row update means another worker has it.
        async with SessionFactory() as session:
            now = utcnow()
            result = await session.execute(
                update(Job)
                .where(Job.id == job_id, Job.state == JobState.QUEUED.value)
                .where((Job.deadline_at.is_(None)) | (Job.deadline_at > now))
                .values(
                    state=JobState.RUNNING.value,
                    lease_owner=self._worker_id,
                    lease_expires_at=now + timedelta(seconds=self.settings.job_lease_seconds),
                    fencing_token=Job.fencing_token + 1,
                    attempt_count=Job.attempt_count + 1,
                    updated_at=now,
                )
                .returning(Job.fencing_token, Job.attempt_count)
            )
            row = result.first()
            await session.commit()
            if row is None:
                return
            fencing_token, attempt_no = int(row[0]), int(row[1])

        handler = HANDLERS.get("")
        job_type = ""
        async with SessionFactory() as session:
            job = await session.get(Job, job_id)
            if job is None:
                return
            job_type = job.type
            handler = HANDLERS.get(job_type)
            if handler is None:
                await self._fail_job(
                    session,
                    job,
                    JobFailure("no_handler", message_key="error.internal.unexpected"),
                    attempt_id=None,
                )
                await session.commit()
                return
            attempt = JobAttempt(
                id=new_id(),
                job_id=job.id,
                attempt_no=attempt_no,
                state="RUNNING",
                worker_id=self._worker_id,
                fencing_token=fencing_token,
                started_at=utcnow(),
            )
            session.add(attempt)
            job.lease_expires_at = utcnow() + timedelta(seconds=self.settings.job_lease_seconds)
            await session.commit()

        heartbeat = asyncio.create_task(self._heartbeat(job_id, fencing_token))
        ctx: JobContext | None = None
        try:
            sem = await self._semaphore_for(job_type)
            async with sem:
                async with SessionFactory() as session:
                    job = await session.get(Job, job_id)
                    if job is None:
                        return
                    project_sem = self._project_slots[job.project_id]
                    ctx = JobContext(
                        session=session,
                        job=job,
                        attempt_id=attempt.id,
                        fencing_token=fencing_token,
                        settings=self.settings,
                        gateway=gateway,
                        search=search,
                        storage=storage,
                        worker_id=self._worker_id,
                    )
                    async with project_sem:
                        await handler(ctx)
                    if job.state == JobState.RUNNING.value:
                        job.state = JobState.SUCCEEDED.value
                        job.completed_at = utcnow()
                        job.active_operation_key = None
                        job.lease_owner = None
                        job.lease_expires_at = None
                        attempt_row = await session.get(JobAttempt, attempt.id)
                        if attempt_row:
                            attempt_row.state = "SUCCEEDED"
                            attempt_row.ended_at = utcnow()
                        await session.commit()
                await self._wake_project_jobs(job.project_id)
        except JobCancelled:
            async with SessionFactory() as session:
                job = await session.get(Job, job_id)
                if job:
                    await self._cancel_job(session, job, attempt.id)
                    await session.commit()
        except JobFailure as failure:
            async with SessionFactory() as session:
                job = await session.get(Job, job_id)
                if job:
                    await self._fail_job(session, job, failure, attempt_id=attempt.id)
                    await session.commit()
            if failure.retryable:
                delay = min(60.0, 2.0 ** attempt_no + random.random())
                self.wake_later(job_id, delay)
        except AppError as exc:
            async with SessionFactory() as session:
                job = await session.get(Job, job_id)
                if job:
                    await self._fail_job(
                        session,
                        job,
                        JobFailure(
                            exc.message_key,
                            category=exc.category,
                            message_key=exc.message_key,
                            retryable=exc.retryable,
                        ),
                        attempt_id=attempt.id,
                    )
                    await session.commit()
            if exc.retryable:
                self.wake_later(job_id, min(60.0, 2.0 ** attempt_no + random.random()))
        except Exception:  # noqa: BLE001
            async with SessionFactory() as session:
                job = await session.get(Job, job_id)
                if job:
                    failure = JobFailure("internal_error", retryable=False)
                    await self._fail_job(session, job, failure, attempt_id=attempt.id)
                    await session.commit()
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat(self, job_id: UUID, fencing_token: int) -> None:
        while True:
            await asyncio.sleep(20)
            async with SessionFactory() as session:
                await session.execute(
                    update(Job)
                    .where(Job.id == job_id, Job.state == JobState.RUNNING.value, Job.fencing_token == fencing_token)
                    .values(lease_expires_at=utcnow() + timedelta(seconds=self.settings.job_lease_seconds))
                )
                await session.commit()

    async def _fail_job(
        self, session: AsyncSession, job: Job, failure: JobFailure, *, attempt_id: UUID | None
    ) -> None:
        if attempt_id:
            attempt = await session.get(JobAttempt, attempt_id)
            if attempt:
                attempt.state = "FAILED"
                attempt.ended_at = utcnow()
                attempt.error_code = failure.code
                attempt.error_class = failure.category
        job.last_error_code = failure.code
        job.last_error_class = failure.category
        job.lease_owner = None
        job.lease_expires_at = None
        if failure.retryable and job.attempt_count < job.max_attempts:
            job.state = JobState.QUEUED.value
            job.active_operation_key = job.active_operation_key
            await events.append(
                session,
                job.project_id,
                "jobResumed",
                {"jobId": str(job.id), "jobType": job.type, "attemptCount": job.attempt_count},
            )
            return
        job.state = JobState.FAILED.value
        job.completed_at = utcnow()
        job.active_operation_key = None
        if job.type in {JobType.PLAN_PAGE.value, JobType.DESIGN_PAGE.value}:
            page_id = (job.payload or {}).get("pageId")
            await events.append(
                session,
                job.project_id,
                "pageJobFailed",
                {
                    "jobId": str(job.id),
                    "pageId": page_id,
                    "kind": "PLAN" if job.type == JobType.PLAN_PAGE.value else "DESIGN",
                    "errorCode": failure.code,
                    "errorCategory": failure.category,
                    "retryable": failure.retryable,
                },
            )
        elif job.type == JobType.EXPORT.value:
            await events.append(
                session,
                job.project_id,
                "exportFailed",
                {
                    "exportId": (job.payload or {}).get("exportId"),
                    "format": (job.payload or {}).get("format"),
                    "errorCode": failure.code,
                    "failedPageIds": [],
                    "validationResult": None,
                },
            )

    async def _cancel_job(self, session: AsyncSession, job: Job, attempt_id: UUID) -> None:
        attempt = await session.get(JobAttempt, attempt_id)
        if attempt:
            attempt.state = "CANCELLED"
            attempt.ended_at = utcnow()
        job.state = JobState.CANCELLED.value
        job.completed_at = utcnow()
        job.active_operation_key = None
        job.lease_owner = None
        job.lease_expires_at = None
        await events.append(
            session,
            job.project_id,
            "jobCancelled",
            {"jobId": str(job.id), "jobType": job.type, "reason": "user_cancelled"},
        )

    async def _wake_project_jobs(self, project_id: UUID) -> None:
        async with SessionFactory() as session:
            rows = (
                await session.scalars(
                    select(Job.id).where(Job.project_id == project_id, Job.state == JobState.QUEUED.value)
                )
            ).all()
        for job_id in rows:
            self.wake(job_id)

    async def reconcile_once(self) -> None:
        now = utcnow()
        async with SessionFactory() as session:
            queued = (
                await session.scalars(
                    select(Job.id)
                    .where(Job.state == JobState.QUEUED.value)
                    .where((Job.deadline_at.is_(None)) | (Job.deadline_at > now))
                    .order_by(Job.priority.desc(), Job.created_at)
                    .limit(200)
                )
            ).all()
            expired = (
                await session.scalars(
                    select(Job).where(
                        Job.state == JobState.QUEUED.value, Job.deadline_at.is_not(None), Job.deadline_at <= now
                    )
                )
            ).all()
            for job in expired:
                job.state = JobState.EXPIRED.value
                job.last_error_code = "deadline_exceeded"
                job.completed_at = now
                job.active_operation_key = None
            stale_running = (
                await session.scalars(
                    select(Job).where(
                        Job.state == JobState.RUNNING.value,
                        Job.lease_expires_at.is_not(None),
                        Job.lease_expires_at < now,
                    )
                )
            ).all()
            for job in stale_running:
                job.state = JobState.QUEUED.value
                job.lease_owner = None
                job.lease_expires_at = None
                await events.append(
                    session,
                    job.project_id,
                    "jobResumed",
                    {"jobId": str(job.id), "jobType": job.type, "attemptCount": job.attempt_count},
                )
            await session.commit()
        for job_id in queued:
            self.wake(job_id)
        for job in stale_running:
            self.wake(job.id)

    async def _reconcile_loop(self) -> None:
        while not self._stopping.is_set():
            await asyncio.sleep(30)
            try:
                await self.reconcile_once()
            except asyncio.CancelledError:
                return
            except Exception:  # noqa: BLE001
                continue


def _stage_for_job(job_type: str) -> str:
    return {
        JobType.INGEST.value: "RESEARCH",
        JobType.DIGEST.value: "RESEARCH",
        JobType.SEARCH.value: "RESEARCH",
        JobType.GAP_SUGGEST.value: "RESEARCH",
        JobType.PROFILE.value: "RESEARCH",
        JobType.OUTLINE.value: "OUTLINE",
        JobType.PLAN_PAGE.value: "PLAN",
        JobType.DESIGN_PAGE.value: "DESIGN",
        JobType.EXPORT.value: "DESIGN",
    }.get(job_type, "INTAKE")


runner = JobRunner()
