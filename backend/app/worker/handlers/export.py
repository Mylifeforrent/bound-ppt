"""Export job handler (EXPORT).

Validation failure is a successful execution of a failed export: the ExportJob
records FAILED and the handler returns after committing. Composition failure is
also recorded on the export row; a real artifact is never claimed without bytes.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from app.core.idempotency import bump_project
from app.core.ids import iso, new_id, utcnow
from app.domain.enums import JobType
from app.models import ExportArtifact, ExportJob, Project
from app.render.pipeline import ExportRenderError, run_render_subprocess
from app.services import export as export_service
from app.services import styles as style_service
from app.services.events import events
from app.worker.runner import JobContext, JobFailure, register


def _uid(raw: object) -> UUID:
    try:
        return UUID(str(raw))
    except (ValueError, TypeError) as exc:
        raise JobFailure("export_missing", category="not_found", message_key="error.not_found.export") from exc


async def _fail_export(
    ctx: JobContext,
    project: Project,
    export: ExportJob,
    *,
    error_code: str,
    report: dict | None,
    failed_page_ids: list[UUID],
) -> None:
    await ctx.check_cancel()
    export.state = "FAILED"
    export.error_code = error_code
    export.error_message_key = (
        "error.export.validation_failed" if error_code == "validation_failed" else "error.internal.unexpected"
    )
    export.validation_report = report
    export.completed_at = utcnow()
    export.progress = {
        "phase": "FAILED",
        "pagesTotal": int((export.deck_snapshot or {}).get("pageCount", 0) or 0),
        "pagesRendered": 0,
        "percent": 0.0,
    }
    bump_project(project)
    await events.append(
        ctx.session,
        project.id,
        "exportFailed",
        {
            "exportId": str(export.id),
            "format": export.format,
            "errorCode": error_code,
            "failedPageIds": [str(page_id) for page_id in failed_page_ids],
            "validationResult": report,
        },
    )
    await ctx.session.commit()


@register(JobType.EXPORT)
async def export_job(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await ctx.session.get(Project, ctx.project_id)
    if project is None:
        raise JobFailure("project_missing", category="not_found", message_key="error.not_found.project")
    export_id = _uid(ctx.payload.get("exportId"))
    export = await ctx.session.get(ExportJob, export_id)
    if export is None or export.project_id != project.id:
        raise JobFailure("export_missing", category="not_found", message_key="error.not_found.export")
    if export.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        return

    export.state = "VALIDATING"
    export.started_at = export.started_at or utcnow()
    await ctx.session.flush()
    await ctx.check_cancel()

    outcome = await export_service.validate_export(ctx.session, project, export)
    export.validation_report = outcome.report
    if not outcome.report.get("passed"):
        await _fail_export(
            ctx,
            project,
            export,
            error_code="validation_failed",
            report=outcome.report,
            failed_page_ids=outcome.failed_page_ids,
        )
        return

    export.state = "COMPOSING"
    export.progress = {
        "phase": "COMPOSING",
        "pagesTotal": int((export.deck_snapshot or {}).get("pageCount", 0) or 0),
        "pagesRendered": 0,
        "percent": 35.0,
    }
    await ctx.session.flush()

    snapshot = export.deck_snapshot or {}
    definition = await style_service.get_style(
        ctx.session, str(snapshot.get("styleKey") or ""), int(snapshot.get("styleVersion") or 1)
    )
    if definition is None:
        raise JobFailure("style_missing", category="validation", message_key="error.validation.unknown_style")
    try:
        theme = style_service.theme_json(definition)
    except KeyError as exc:
        raise JobFailure(
            "style_missing", category="validation", message_key="error.validation.unknown_style"
        ) from exc

    render_input = export_service.build_render_input(snapshot, outcome.bodies, theme)
    await ctx.check_cancel()
    try:
        data, file_name = await run_render_subprocess(
            render_input, export.format, float(ctx.settings.export_timeout_seconds)
        )
    except ExportRenderError:
        await _fail_export(
            ctx,
            project,
            export,
            error_code="render_failed",
            report=outcome.report,
            failed_page_ids=[],
        )
        return

    await ctx.check_cancel()
    _ext, mime_type = export_service.format_meta(export.format)
    object_key = f"projects/{project.id}/exports/{export.id}/{file_name}"
    result = ctx.storage.put_bytes(object_key, data, mime_type)
    if hasattr(result, "__await__"):
        await result
    checksum = hashlib.sha256(data).hexdigest()
    expires_at = utcnow() + export_service.ARTIFACT_TTL
    theme_fonts = {
        str(font)
        for font in ((render_input.get("theme") or {}).get("fonts") or {}).values()
        if font
    }
    substitutions = [
        {
            "from": font,
            "to": "system fallback",
            "reason": "The M1 export does not embed font binaries; the viewer may substitute this family.",
        }
        for font in sorted(theme_fonts)
    ]

    artifact = ExportArtifact(
        id=new_id(),
        export_job_id=export.id,
        project_id=project.id,
        object_key=object_key,
        checksum=checksum,
        byte_size=len(data),
        mime_type=mime_type,
        file_name=file_name,
        substitution_report={"substitutions": substitutions},
        created_at=utcnow(),
        expires_at=expires_at,
    )
    ctx.session.add(artifact)
    await ctx.session.flush()

    page_count = int(snapshot.get("pageCount", 0) or 0)
    export.state = "SUCCEEDED"
    export.completed_at = utcnow()
    export.progress = {
        "phase": "SUCCEEDED",
        "pagesTotal": page_count,
        "pagesRendered": page_count,
        "percent": 100.0,
    }
    bump_project(project)
    await events.append(
        ctx.session,
        project.id,
        "exportProgress",
        {
            "exportId": str(export.id),
            "format": export.format,
            "phase": "COMPOSING",
            "pagesRendered": page_count,
            "pagesTotal": page_count,
            "percent": 100.0,
        },
    )
    await events.append(
        ctx.session,
        project.id,
        "exportDone",
        {
            "exportId": str(export.id),
            "format": export.format,
            "artifactId": str(artifact.id),
            "byteSize": artifact.byte_size,
            "checksum": checksum,
            "expiresAt": iso(expires_at),
        },
    )
    await ctx.session.flush()
    await ctx.check_cancel()
    await ctx.session.commit()
