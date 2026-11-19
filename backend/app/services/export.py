"""Export command, snapshot, validation and DTO assembly.

The export job freezes a deck snapshot at request time. Composition runs in a
subprocess with no database or provider credentials; the parent commits the
artifact only after the output exists with non-zero size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import gate, not_found, validation
from app.core.idempotency import bump_project
from app.core.ids import iso, new_id, utcnow
from app.domain import layouts as layout_domain
from app.domain.enums import ArtifactKind, ExportFormat, PageStatus
from app.models import (
    ArtifactVersion,
    ExportArtifact,
    ExportJob,
    Job,
    Project,
)
from app.render.pipeline import MIME_TYPES, OUTPUT_NAMES
from app.schemas.dto import (
    DeckSnapshotDTO,
    ExportArtifactDTO,
    ExportDTO,
    ExportProgressDTO,
    ExportValidationCheckDTO,
    ExportValidationDTO,
    PageError,
    SubstitutionReportDTO,
)
from app.services import artifacts, generation, state
from app.services import jobs as job_service

ARTIFACT_TTL = timedelta(days=7)


def format_meta(fmt: str) -> tuple[str, str]:
    value = (fmt or "").upper()
    if value not in {item.value for item in ExportFormat}:
        raise validation(
            "error.validation.invalid_request",
            {"field": "format", "allowed": [item.value for item in ExportFormat]},
        )
    return OUTPUT_NAMES[value], MIME_TYPES[value]


async def _all_pages_current(session: AsyncSession, project: Project) -> state.PageListDTO:
    page_list = await state.build_page_list(session, project)
    if not page_list.pages:
        raise gate("error.gate.design_incomplete", {"reason": "no_pages"})
    for page in page_list.pages:
        if page.design.status != PageStatus.DONE.value:
            raise gate(
                "error.gate.design_incomplete",
                {"pageId": str(page.page_id), "status": page.design.status},
            )
    return page_list


async def build_deck_snapshot(session: AsyncSession, project: Project, fmt: str) -> dict[str, Any]:
    page_list = await _all_pages_current(session, project)
    selection, definition = await state.load_style_selection(session, project)
    if selection is None or definition is None:
        raise gate("error.gate.style_not_selected")
    bundle = await state.load_outline(session, project)
    if bundle.version is None:
        raise gate("error.gate.design_incomplete")

    pages: list[dict[str, Any]] = []
    design_version_ids: dict[str, str] = {}
    for summary in page_list.pages:
        page_row = bundle.by_page.get(summary.page_id)
        if page_row is None or summary.design.artifact_version_id is None:
            raise gate("error.gate.design_incomplete", {"pageId": str(summary.page_id)})
        _chrome, label = generation.page_chrome(page_row, bundle)
        pages.append(
            {
                "pageId": str(summary.page_id),
                "position": page_row.position,
                "title": page_row.title,
                "pageType": page_row.page_type,
                "sectionLabel": label,
                "chromeVersion": _chrome,
            }
        )
        design_version_ids[str(summary.page_id)] = str(summary.design.artifact_version_id)
    page_count = len(pages)
    return {
        "version": 1,
        "format": fmt,
        "pageCount": page_count,
        "renderedCount": page_count,
        "styleKey": definition.key,
        "styleVersion": selection.style_version,
        "pageIds": [page["pageId"] for page in pages],
        "designVersionIds": design_version_ids,
        "pages": pages,
        "createdAt": iso(utcnow()),
    }


@dataclass
class StartExportResult:
    export: ExportJob
    job: Job


async def start_export(session: AsyncSession, project: Project, fmt: str) -> StartExportResult:
    value = (fmt or "").upper()
    format_meta(value)
    snapshot = await build_deck_snapshot(session, project, value)
    export = ExportJob(
        id=new_id(),
        project_id=project.id,
        format=value,
        state="QUEUED",
        deck_snapshot=snapshot,
        validation_report=None,
        progress={
            "phase": "QUEUED",
            "pagesTotal": snapshot["pageCount"],
            "pagesRendered": 0,
            "percent": 0.0,
        },
        created_at=utcnow(),
    )
    session.add(export)
    await session.flush()
    job = await job_service.enqueue_job(
        session,
        project,
        "EXPORT",
        operation_key=f"export:{export.id}",
        payload={"exportId": str(export.id), "format": value},
        priority=1,
    )
    bump_project(project)
    await session.flush()
    return StartExportResult(export=export, job=job)


async def load_export(session: AsyncSession, project: Project, export_id: UUID) -> ExportJob:
    export = await session.scalar(
        select(ExportJob).where(ExportJob.id == export_id, ExportJob.project_id == project.id)
    )
    if export is None:
        raise not_found("error.not_found.export")
    return export


async def load_artifact(session: AsyncSession, export_id: UUID) -> ExportArtifact | None:
    return await session.scalar(
        select(ExportArtifact).where(ExportArtifact.export_job_id == export_id)
    )


def _validation_dto(report: dict[str, Any] | None) -> ExportValidationDTO | None:
    if not report:
        return None
    checks = [
        ExportValidationCheckDTO(
            code=str(item.get("code") or ""),
            status=str(item.get("status") or "SKIP"),
            page_ids=[UUID(str(pid)) for pid in item.get("pageIds") or [] if _is_uuid(str(pid))],
        )
        for item in report.get("checks") or []
    ]
    failed = [
        ExportValidationCheckDTO(
            code=str(item.get("code") or ""),
            status=str(item.get("status") or "FAIL"),
            page_ids=[UUID(str(pid)) for pid in item.get("pageIds") or [] if _is_uuid(str(pid))],
        )
        for item in report.get("failedChecks") or []
    ]
    return ExportValidationDTO(passed=bool(report.get("passed")), checks=checks, failed_checks=failed)


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, TypeError):
        return False


def _progress_dto(export: ExportJob) -> ExportProgressDTO:
    raw = export.progress or {}
    total = int(raw.get("pagesTotal", (export.deck_snapshot or {}).get("pageCount", 0)) or 0)
    rendered = int(raw.get("pagesRendered", 0) or 0)
    percent = float(raw.get("percent", (rendered / total * 100.0) if total else 0.0) or 0.0)
    return ExportProgressDTO(
        phase=str(raw.get("phase") or export.state),
        pages_total=total,
        pages_rendered=rendered,
        percent=percent,
    )


def _error_dto(export: ExportJob) -> PageError | None:
    if not export.error_code:
        return None
    return PageError(
        code=export.error_code,
        category="export_validation_failure" if export.error_code == "validation_failed" else "internal",
        message_key=export.error_message_key or "error.export.validation_failed",
        retryable=True,
    )


def _artifact_dto(export: ExportJob, artifact: ExportArtifact | None) -> ExportArtifactDTO | None:
    if artifact is None:
        return None
    return ExportArtifactDTO(
        artifact_id=artifact.id,
        file_name=artifact.file_name,
        mime_type=artifact.mime_type,
        byte_size=artifact.byte_size,
        checksum=artifact.checksum,
        created_at=artifact.created_at or datetime.min,
        expires_at=artifact.expires_at,
        download_path=f"/api/exports/{export.id}/download",
    )


def export_dto(export: ExportJob, artifact: ExportArtifact | None) -> ExportDTO:
    snapshot = export.deck_snapshot or {}
    return ExportDTO(
        export_id=export.id,
        project_id=export.project_id,
        format=export.format,
        state=export.state,
        deck_snapshot=DeckSnapshotDTO(
            page_count=int(snapshot.get("pageCount", 0) or 0),
            style_key=str(snapshot.get("styleKey") or "unknown"),
            rendered_count=int(snapshot.get("renderedCount", 0) or 0),
            excluded_page_ids=[],
        ),
        progress=_progress_dto(export),
        validation=_validation_dto(export.validation_report),
        artifact=_artifact_dto(export, artifact),
        substitution_report=(
            SubstitutionReportDTO(substitutions=list((artifact.substitution_report or {}).get("substitutions") or []))
            if artifact is not None and artifact.substitution_report is not None
            else None
        ),
        error=_error_dto(export),
        created_at=export.created_at or datetime.min,
        started_at=export.started_at,
        completed_at=export.completed_at,
    )


# ---- Validation ------------------------------------------------------------


@dataclass
class ValidationOutcome:
    report: dict[str, Any]
    bodies: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_page_ids: list[UUID] = field(default_factory=list)


def _check(code: str, status: str, page_ids: list[UUID] | None = None) -> dict[str, Any]:
    return {"code": code, "status": status, "pageIds": [str(pid) for pid in (page_ids or [])]}


def body_visible_text(body: dict[str, Any]) -> str:
    chunks: list[str] = []
    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    if meta.get("title"):
        chunks.append(str(meta["title"]))
    for block in body.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        if block.get("text"):
            chunks.append(str(block["text"]))
        for item in block.get("items") or []:
            chunks.append(str(item))
    return "\n".join(chunks).strip()


async def validate_export(
    session: AsyncSession, project: Project, export: ExportJob
) -> ValidationOutcome:
    snapshot = export.deck_snapshot or {}
    snapshot_ids = [str(pid) for pid in snapshot.get("pageIds") or []]
    version_ids = dict(snapshot.get("designVersionIds") or {})
    bundle = await state.load_outline(session, project)
    page_list = await state.build_page_list(session, project)
    status_by_page = {str(page.page_id): page.design.status for page in page_list.pages}
    current_ids = [str(page.page_id) for page in bundle.pages]
    checks: list[dict[str, Any]] = []

    if current_ids != snapshot_ids:
        mismatch = {UUID(pid) for pid in snapshot_ids if _is_uuid(pid)} ^ {
            UUID(pid) for pid in current_ids if _is_uuid(pid)
        }
        checks.append(_check("page_count_mismatch", "FAIL", sorted(mismatch)))
    else:
        checks.append(_check("page_count_mismatch", "PASS"))

    missing: list[UUID] = []
    bodies: dict[str, dict[str, Any]] = {}
    for page_id in snapshot_ids:
        if status_by_page.get(page_id) != PageStatus.DONE.value:
            missing.append(UUID(page_id))
            continue
        pointer = await artifacts.pointer_for(session, project, UUID(page_id), ArtifactKind.DESIGN.value)
        expected_version_id = version_ids.get(page_id)
        if pointer is None or expected_version_id is None or str(pointer.artifact_version_id) != expected_version_id:
            missing.append(UUID(page_id))
            continue
        version = await session.get(ArtifactVersion, pointer.artifact_version_id)
        if version is None or version.kind != ArtifactKind.DESIGN.value:
            missing.append(UUID(page_id))
            continue
        bodies[page_id] = await artifacts.read_artifact_body(version)
    checks.append(_check("missing_design", "FAIL" if missing else "PASS", missing))

    empty: list[UUID] = []
    blocked: list[UUID] = []
    out_of_bounds: list[UUID] = []
    overflow: list[UUID] = []
    for page_id, body in bodies.items():
        text = body_visible_text(body)
        if not text:
            empty.append(UUID(page_id))
        if len(text) > 1400:
            overflow.append(UUID(page_id))
        canvas = body.get("canvas") if isinstance(body.get("canvas"), dict) else layout_domain.layouts()["canvas"]
        canvas_w = int(canvas.get("width", 1280) or 1280)
        canvas_h = int(canvas.get("height", 720) or 720)
        for asset in body.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            if str(asset.get("licenseStatus") or asset.get("license_status") or "") == "BLOCKED":
                blocked.append(UUID(page_id))
                continue
            width = int(asset.get("width") or 0)
            height = int(asset.get("height") or 0)
            if width <= 0 or height <= 0 or width > canvas_w or height > canvas_h:
                out_of_bounds.append(UUID(page_id))
    checks.append(_check("empty_page", "FAIL" if empty else "PASS", empty))
    checks.append(_check("license_blocked", "FAIL" if blocked else "PASS", blocked))
    checks.append(_check("asset_out_of_bounds", "FAIL" if out_of_bounds else "PASS", out_of_bounds))
    checks.append(_check("text_overflow", "WARN" if overflow else "PASS", overflow))
    theme = layout_domain.themes().get(str(snapshot.get("styleKey") or ""), {})
    fonts = {str(font) for font in (theme.get("fonts") or {}).values() if font}
    # M1 does not embed font binaries; the report names the substitution risk
    # instead of silently relying on the viewer (FR-6.17).
    checks.append(_check("fonts_missing", "WARN" if fonts else "PASS"))
    checks.append(_check("html_external_ref", "SKIP"))
    checks.append(_check("render_incomplete", "PASS" if len(bodies) == int(snapshot.get("pageCount", 0)) else "FAIL", missing))

    failed = [item for item in checks if item["status"] == "FAIL"]
    failed_ids: list[UUID] = []
    for item in failed:
        for pid in item.get("pageIds") or []:
            if _is_uuid(pid):
                failed_ids.append(UUID(pid))
    report = {"passed": not failed, "checks": checks, "failedChecks": failed}
    return ValidationOutcome(report=report, bodies=bodies, failed_page_ids=list(dict.fromkeys(failed_ids)))


def build_render_input(
    snapshot: dict[str, Any],
    bodies: dict[str, dict[str, Any]],
    theme: dict[str, Any],
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for page in snapshot.get("pages") or []:
        body = bodies.get(str(page.get("pageId")))
        if body is None:
            continue
        pages.append({**page, "body": body})
    return {
        "format": snapshot.get("format"),
        "styleKey": snapshot.get("styleKey"),
        "styleVersion": snapshot.get("styleVersion"),
        "theme": theme,
        "layouts": layout_domain.layouts(),
        "pages": pages,
    }
