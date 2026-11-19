"""Material service helpers shared by the materials API and the research handlers.

Rules enforced here:
- project-scope authorization is the API layer's job (`load_owned_project`);
- material gates are ordered: project active, consent, limit, stage;
- events never carry material text, file names or full URLs.
"""

from __future__ import annotations

import inspect
import re
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, gate, not_found, validation
from app.core.ids import utcnow
from app.domain.enums import JobState, JobType, MaterialStatus, ProjectStatus, Stage
from app.ingest import parsers
from app.models import Job, Material, Project, SourceItem
from app.schemas.dto import ActiveJobRef, MaterialDTO, MaterialListDTO, PageError
from app.services.events import events
from app.services.jobs import enqueue_job
from app.storage import ALLOWED_UPLOAD_TYPES, file_content_type, storage

MUTABLE_MATERIAL_STAGES = {Stage.INTAKE.value, Stage.RESEARCH.value}
ACTIVE_JOB_STATES = (JobState.QUEUED.value, JobState.RUNNING.value)
ASSET_JOB_TYPES = (JobType.INGEST.value, JobType.DIGEST.value)

_PARSE_ERROR_CODES = {
    "url_unreachable",
    "type_mismatch",
    "parse_failed",
    "parser_error",
    "content_missing",
}
_VALIDATION_ERROR_CODES = {
    "file_too_large",
    "unsupported_type",
    "invalid_url",
    "upload_missing",
}


async def maybe_await(value: Any) -> Any:
    """Storage adapters may be sync (local) or async (S3)."""
    if inspect.isawaitable(value):
        return await value
    return value


async def count_materials(session: AsyncSession, project_id: UUID) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(Material)
            .where(Material.project_id == project_id, Material.status != MaterialStatus.REMOVED.value)
        )
        or 0
    )


async def list_active_materials(session: AsyncSession, project: Project) -> list[Material]:
    return list(
        (
            await session.scalars(
                select(Material)
                .where(
                    Material.project_id == project.id,
                    Material.status != MaterialStatus.REMOVED.value,
                )
                .order_by(Material.created_at, Material.id)
            )
        ).all()
    )


async def assert_project_active(project: Project) -> None:
    if project.status != ProjectStatus.ACTIVE.value:
        raise not_found("error.not_found.project")


async def assert_material_stage_mutable(project: Project) -> None:
    if project.stage not in MUTABLE_MATERIAL_STAGES:
        raise gate("error.gate.material_locked", {"restartRequired": True})


async def assert_add_allowed(session: AsyncSession, project: Project, user: Any) -> int:
    """Admission gates for adding a material, in contract order."""
    await assert_project_active(project)
    # Local import keeps the service free of an API-package import cycle.
    from app.api.v1.system import has_consent

    if not await has_consent(session, user):
        raise gate("error.gate.consent_required", {"noticeType": "DATA_NOTICE"})
    settings = get_settings()
    count = await count_materials(session, project.id)
    if count >= settings.material_max_count:
        raise gate(
            "error.gate.material_limit",
            {"limit": settings.material_max_count, "currentCount": count},
        )
    await assert_material_stage_mutable(project)
    return count


async def assert_finalize_allowed(session: AsyncSession, project: Project) -> None:
    """Finalize is a material mutation; consent was checked at upload-url time."""
    await assert_project_active(project)
    await assert_material_stage_mutable(project)


def validate_paste(text: str) -> str:
    """Paste is content-bearing; callers must never log the return value."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise validation("error.validation.empty_paste")
    if len(cleaned) > get_settings().ingest_max_chars:
        raise validation("error.validation.invalid_request", {"field": "text"})
    return cleaned


def normalize_material_url(raw: str) -> tuple[str, str]:
    """Return (normalized_url, hostname); raises validation.invalid_url."""
    url = parsers.normalize_url(raw)
    return url, urlparse(url).hostname or ""


def validate_upload_request(file_name: str, mime_type: str, size_bytes: int) -> tuple[str, str]:
    """Validate the presign request. Returns (canonical_mime, object_key_suffix)."""
    settings = get_settings()
    clean_name = (file_name or "").strip()
    suffix = parsers.normalize_filename_extension(clean_name)
    if not clean_name or suffix not in ALLOWED_UPLOAD_TYPES:
        raise validation("error.validation.unsupported_type")
    if size_bytes <= 0 or size_bytes > settings.upload_max_bytes:
        raise validation("error.validation.file_too_large")
    expected = ALLOWED_UPLOAD_TYPES[suffix]
    declared = (mime_type or "").strip().lower().split(";", 1)[0]
    if declared and declared != "application/octet-stream" and declared != expected:
        raise AppError("parse_failure", "error.parse.type_mismatch")
    return expected, file_content_type(clean_name)


async def get_active_material(session: AsyncSession, project: Project, material_id: UUID) -> Material:
    material = await session.scalar(
        select(Material).where(
            Material.id == material_id,
            Material.project_id == project.id,
            Material.status != MaterialStatus.REMOVED.value,
        )
    )
    if material is None:
        raise not_found("error.not_found.material")
    return material


def material_error(material: Material) -> PageError | None:
    if not material.error_code:
        return None
    code = material.error_code
    if code in _PARSE_ERROR_CODES:
        category = "parse_failure"
    elif code in _VALIDATION_ERROR_CODES:
        category = "validation"
    else:
        category = "parse_failure"
    return PageError(
        code=code,
        category=category,
        message_key=material.error_message_key or f"error.parse.{code}",
        retryable=False,
    )


def active_job_ref(job: Job | None) -> ActiveJobRef | None:
    if job is None:
        return None
    page_id = None
    raw_page = (job.payload or {}).get("pageId")
    if raw_page:
        try:
            page_id = UUID(str(raw_page))
        except (TypeError, ValueError):
            page_id = None
    return ActiveJobRef(job_id=job.id, type=job.type, state=job.state, page_id=page_id)


def material_dto(material: Material, active_job: Job | None = None) -> MaterialDTO:
    return MaterialDTO(
        id=material.id,
        kind=material.kind,
        status=material.status,
        display_name=material.display_name,
        mime_type=material.mime_type,
        size_bytes=int(material.size_bytes or 0),
        page_count=material.page_count,
        domain=material.domain,
        error=material_error(material),
        created_at=material.created_at,
        updated_at=material.updated_at,
        active_job=active_job_ref(active_job),
    )


async def active_jobs_by_material(
    session: AsyncSession, project: Project, *, job_types: tuple[str, ...] = (JobType.INGEST.value,)
) -> dict[UUID, Job]:
    rows = list(
        (
            await session.scalars(
                select(Job)
                .where(
                    Job.project_id == project.id,
                    Job.state.in_(ACTIVE_JOB_STATES),
                    Job.type.in_(job_types),
                )
                .order_by(Job.created_at)
            )
        ).all()
    )
    result: dict[UUID, Job] = {}
    for job in rows:
        raw = (job.payload or {}).get("materialId")
        if not raw:
            continue
        try:
            result.setdefault(UUID(str(raw)), job)
        except (TypeError, ValueError):
            continue
    return result


async def build_material_list(session: AsyncSession, project: Project) -> MaterialListDTO:
    settings = get_settings()
    materials = await list_active_materials(session, project)
    active = await active_jobs_by_material(session, project)
    return MaterialListDTO(
        materials=[material_dto(m, active.get(m.id)) for m in materials],
        limit=settings.material_max_count,
        remaining=max(0, settings.material_max_count - len(materials)),
    )


def material_status_payload(
    material: Material, project_version: int, *, error_code: str | None = None
) -> dict[str, Any]:
    """Content-free `materialStatusChanged` payload [API §6]."""
    payload: dict[str, Any] = {
        "materialId": str(material.id),
        "kind": material.kind,
        "status": material.status,
        "projectVersion": project_version,
    }
    if error_code:
        payload["errorCode"] = error_code
    if material.page_count is not None:
        payload["pageCountBucket"] = page_count_bucket(material.page_count)
    return payload


def page_count_bucket(page_count: int) -> str:
    if page_count <= 0:
        return "none"
    if page_count < 10:
        return "lt10"
    if page_count < 50:
        return "10_49"
    return "gte50"


def source_summary(text: str, limit: int = 240) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)] + "…"


def material_ingest_operation_key(material_id: UUID) -> str:
    return f"ingest:{material_id}"


def material_digest_operation_key(material_id: UUID) -> str:
    return f"digest:{material_id}"


async def enqueue_ingest(session: AsyncSession, project: Project, material: Material) -> Job:
    return await enqueue_job(
        session,
        project,
        JobType.INGEST,
        operation_key=material_ingest_operation_key(material.id),
        active_operation_key=material_ingest_operation_key(material.id),
        payload={"materialId": str(material.id), "kind": material.kind},
    )


async def enqueue_digest(session: AsyncSession, project: Project, material: Material) -> Job:
    return await enqueue_job(
        session,
        project,
        JobType.DIGEST,
        operation_key=material_digest_operation_key(material.id),
        active_operation_key=material_digest_operation_key(material.id),
        payload={"materialId": str(material.id)},
    )


async def has_current_digest(session: AsyncSession, material_id: UUID) -> bool:
    from app.models import MaterialDigest

    row = await session.scalar(
        select(MaterialDigest.id).where(
            MaterialDigest.material_id == material_id,
            MaterialDigest.is_current.is_(True),
        )
    )
    return row is not None


async def current_digest(session: AsyncSession, material_id: UUID):
    from app.models import MaterialDigest

    return await session.scalar(
        select(MaterialDigest)
        .where(MaterialDigest.material_id == material_id, MaterialDigest.is_current.is_(True))
        .order_by(MaterialDigest.version.desc())
        .limit(1)
    )


async def materials_missing_digest(session: AsyncSession, project: Project) -> list[Material]:
    materials = await list_active_materials(session, project)
    missing: list[Material] = []
    for material in materials:
        if material.status != MaterialStatus.DIGESTED.value:
            continue
        if not material.content_ref:
            continue
        if not await has_current_digest(session, material.id):
            missing.append(material)
    return missing


async def cancel_jobs_for_material(session: AsyncSession, project: Project, material_id: UUID) -> list[UUID]:
    """Cancel queued ingest/digest jobs and flag running ones for cooperative cancel."""
    rows = list(
        (
            await session.scalars(
                select(Job).where(
                    Job.project_id == project.id,
                    Job.state.in_(ACTIVE_JOB_STATES),
                    Job.type.in_(ASSET_JOB_TYPES),
                )
            )
        ).all()
    )
    cancelled: list[UUID] = []
    now = utcnow()
    for job in rows:
        raw = (job.payload or {}).get("materialId")
        try:
            matches = raw is not None and UUID(str(raw)) == material_id
        except (TypeError, ValueError):
            matches = False
        if not matches:
            continue
        if job.state == JobState.QUEUED.value:
            job.state = JobState.CANCELLED.value
            job.completed_at = now
            job.active_operation_key = None
            cancelled.append(job.id)
            await events.append(
                session,
                project.id,
                "jobCancelled",
                {"jobId": str(job.id), "jobType": job.type, "reason": "material_removed"},
            )
        elif job.cancel_requested_at is None:
            job.cancel_requested_at = now
    return cancelled


async def delete_material_objects(material: Material) -> None:
    """Best-effort object cleanup; orphan sweeper handles partial failures."""
    for key in (material.content_ref, material.raw_ref):
        if not key:
            continue
        try:
            exists = await maybe_await(storage.exists(key))
            if exists:
                await maybe_await(storage.delete(key))
        except Exception:  # noqa: BLE001 - deletion is best effort
            continue


async def material_source_count(session: AsyncSession, project: Project) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(SourceItem)
            .where(SourceItem.project_id == project.id, SourceItem.origin == "PROVIDED")
        )
        or 0
    )


async def infer_file_name(material: Material) -> str:
    if material.raw_ref:
        suffix = parsers.normalize_filename_extension(material.raw_ref)
        if suffix:
            return f"material{suffix}"
    mime = (material.mime_type or "").lower()
    reverse = {
        "application/pdf": "material.pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "material.docx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "material.xlsx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "material.pptx",
        "text/markdown": "material.md",
        "text/plain": "material.txt",
        "text/csv": "material.csv",
    }
    return reverse.get(mime, "material.bin")


def error_code_from(exc: AppError) -> str:
    return exc.message_key.rsplit(".", 1)[-1] or exc.category


__all__ = [
    "MUTABLE_MATERIAL_STAGES",
    "assert_add_allowed",
    "assert_finalize_allowed",
    "assert_material_stage_mutable",
    "assert_project_active",
    "build_material_list",
    "cancel_jobs_for_material",
    "count_materials",
    "current_digest",
    "delete_material_objects",
    "enqueue_digest",
    "enqueue_ingest",
    "error_code_from",
    "get_active_material",
    "has_current_digest",
    "infer_file_name",
    "list_active_materials",
    "material_dto",
    "material_error",
    "material_source_count",
    "material_status_payload",
    "materials_missing_digest",
    "maybe_await",
    "normalize_material_url",
    "source_summary",
    "validate_paste",
    "validate_upload_request",
]
