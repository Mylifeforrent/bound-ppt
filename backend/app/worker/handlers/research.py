"""Research-stage job handlers (INGEST, DIGEST, SEARCH, GAP_SUGGEST).

The runner owns the terminal job state; these handlers only own the research
rows, durable events and follow-up jobs. Provider calls happen before the
handler's write transaction, and every event payload stays content-free.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import func, select, update

from app.core.errors import AppError
from app.core.ids import new_id
from app.domain.enums import JobType, MaterialStatus, SourceOrigin, SourceType
from app.ingest import parsers
from app.ingest.search import SearchOutcome
from app.models import GapSuggestion, Job, Material, MaterialDigest, Project, SourceItem
from app.services import materials as material_service
from app.services import research as research_service
from app.services.events import events
from app.services.jobs import wake_jobs
from app.worker.runner import JobContext, JobFailure, register


def _payload_uuid(raw: Any) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except (TypeError, ValueError):
        return None


async def _load_project_material(ctx: JobContext) -> tuple[Project, Material] | tuple[None, None]:
    project = await ctx.session.get(Project, ctx.project_id)
    material_id = _payload_uuid(ctx.payload.get("materialId"))
    if project is None or material_id is None:
        return None, None
    material = await ctx.session.get(Material, material_id)
    if (
        material is None
        or material.project_id != project.id
        or material.status == MaterialStatus.REMOVED.value
    ):
        return None, None
    return project, material


async def _read_material(ctx: JobContext, material: Material) -> parsers.ParsedMaterial:
    """Parse content off the event loop; every failure is a typed AppError."""
    settings = ctx.settings
    if material.kind == "PASTE":
        if not material.content_ref:
            raise AppError("parse_failure", "error.parse.content_missing")
        try:
            data = await material_service.maybe_await(ctx.storage.get_bytes(material.content_ref))
            text = data.decode("utf-8", errors="replace").replace("\x00", "").strip()
        except Exception as exc:  # noqa: BLE001 - storage adapter boundary
            raise AppError("parse_failure", "error.parse.content_missing") from exc
        if not text:
            raise AppError("parse_failure", "error.parse.content_missing")
        return parsers.ParsedMaterial(
            text=text[: settings.ingest_max_chars], page_count=None, mime_type="text/plain"
        )
    if material.kind == "URL":
        if not material.source_url:
            raise AppError("parse_failure", "error.parse.url_unreachable")
        return await parsers.fetch_url(material.source_url)
    if material.kind == "FILE":
        if not material.raw_ref:
            raise AppError("parse_failure", "error.parse.content_missing")
        try:
            data = await material_service.maybe_await(ctx.storage.get_bytes(material.raw_ref))
        except Exception as exc:  # noqa: BLE001 - storage adapter boundary
            raise AppError("parse_failure", "error.parse.content_missing") from exc
        file_name = await material_service.infer_file_name(material)
        return await asyncio.to_thread(parsers.parse_file, file_name, data)
    raise AppError("parse_failure", "error.parse.content_missing")


async def _read_text(ctx: JobContext, material: Material) -> str | None:
    if not material.content_ref:
        return None
    try:
        data = await material_service.maybe_await(ctx.storage.get_bytes(material.content_ref))
    except Exception:  # noqa: BLE001 - storage adapter boundary
        return None
    text = data.decode("utf-8", errors="replace").replace("\x00", "").strip()
    return text or None


async def _mark_material_failed(
    ctx: JobContext, project: Project, material: Material, code: str, message_key: str
) -> None:
    material.status = MaterialStatus.FAILED.value
    material.error_code = code
    material.error_message_key = message_key
    await ctx.session.flush()
    await events.append(
        ctx.session,
        project.id,
        "materialStatusChanged",
        material_service.material_status_payload(material, project.version, error_code=code),
    )
    await ctx.session.commit()


async def _maybe_enqueue_gap_suggest(ctx: JobContext, project: Project) -> Job | None:
    if not await research_service.all_materials_digested(ctx.session, project):
        return None
    if await research_service.latest_gap_batch(ctx.session, project) is not None:
        return None
    return await research_service.enqueue_gap_suggest(ctx.session, project)


@register(JobType.INGEST)
async def ingest_material(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project, material = await _load_project_material(ctx)
    if project is None or material is None:
        return

    material.status = MaterialStatus.INGESTING.value
    await ctx.session.flush()
    # Parsing a URL or a large file may take seconds; never hold the transaction.
    await ctx.session.commit()
    try:
        parsed = await _read_material(ctx, material)
    except AppError as exc:
        code = material_service.error_code_from(exc)
        await _mark_material_failed(ctx, project, material, code, exc.message_key)
        return

    content_ref = material.content_ref or parsers.material_content_key(
        str(project.id), str(material.id)
    )
    encoded = parsed.text.encode("utf-8")
    await material_service.maybe_await(
        ctx.storage.put_bytes(content_ref, encoded, parsed.mime_type or "text/plain")
    )
    material.content_ref = content_ref
    material.mime_type = parsed.mime_type or material.mime_type
    material.page_count = parsed.page_count
    if material.kind == "URL" and parsed.title:
        material.display_name = parsed.title.strip()[:200] or material.display_name
    if not material.size_bytes:
        material.size_bytes = len(encoded)
    material.status = MaterialStatus.DIGESTED.value
    material.error_code = None
    material.error_message_key = None
    await ctx.session.flush()

    source = await ctx.session.scalar(
        select(SourceItem).where(
            SourceItem.project_id == project.id,
            SourceItem.origin == SourceOrigin.PROVIDED.value,
            SourceItem.material_id == material.id,
        )
    )
    created_source: SourceItem | None = None
    if source is None:
        created_source = SourceItem(
            id=new_id(),
            project_id=project.id,
            origin=SourceOrigin.PROVIDED.value,
            source_type=str(material.kind),
            title=material.display_name,
            summary=material_service.source_summary(parsed.text),
            domain=material.domain,
            url_hash=parsers.url_hash(material.source_url) if material.source_url else None,
            content_ref=content_ref,
            material_id=material.id,
            gap_suggestion_id=None,
            rank=0,
        )
        ctx.session.add(created_source)
        await ctx.session.flush()

    await events.append(
        ctx.session,
        project.id,
        "materialStatusChanged",
        material_service.material_status_payload(material, project.version),
    )
    if created_source is not None:
        await events.append(
            ctx.session,
            project.id,
            "sourceAdded",
            research_service.source_added_payload(created_source),
        )

    digest_job: Job | None = None
    if not await material_service.has_current_digest(ctx.session, material.id):
        digest_job = await material_service.enqueue_digest(ctx.session, project, material)

    await ctx.session.commit()
    if digest_job is not None and digest_job.state == "QUEUED":
        wake_jobs(digest_job)


@register(JobType.DIGEST)
async def digest_material(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project, material = await _load_project_material(ctx)
    if project is None or material is None:
        return

    # Storage reads can be remote (S3); close the read transaction first.
    await ctx.session.commit()
    text = await _read_text(ctx, material)
    if text is None:
        await _mark_material_failed(
            ctx, project, material, "content_missing", "error.parse.content_missing"
        )
        return

    existing = await material_service.current_digest(ctx.session, material.id)
    if existing is not None and existing.status == "READY":
        gap_job = await _maybe_enqueue_gap_suggest(ctx, project)
        await ctx.session.commit()
        if gap_job is not None and gap_job.state == "QUEUED":
            wake_jobs(gap_job)
        return

    # No writes have happened yet: close the read transaction before the model call.
    await ctx.session.commit()
    result = await ctx.gateway.digest(text, material.display_name)
    digest_out = result.value

    await ctx.session.execute(
        update(MaterialDigest)
        .where(MaterialDigest.material_id == material.id, MaterialDigest.is_current.is_(True))
        .values(is_current=False)
    )
    latest = await ctx.session.scalar(
        select(func.max(MaterialDigest.version)).where(MaterialDigest.material_id == material.id)
    )
    version = int(latest or 0) + 1
    digest_row = MaterialDigest(
        id=new_id(),
        project_id=project.id,
        material_id=material.id,
        version=version,
        is_current=True,
        status="READY",
        digest_ref=None,
        summary_preview=material_service.source_summary(str(digest_out.summary), 280),
        extracted_char_count=len(text),
        length_bucket=str(digest_out.length_bucket),
        parser_profile_version="v1",
        producer_job_id=ctx.job.id,
    )
    ctx.session.add(digest_row)
    await ctx.session.flush()

    usage = result.usage
    await ctx.usage(
        capability="digest",
        unit_type="tokens",
        quantity=float(usage.input_tokens + usage.output_tokens),
        provider=usage.provider,
        estimated_cost=usage.estimated_cost,
    )
    await events.append(
        ctx.session,
        project.id,
        "digestReady",
        research_service.digest_ready_payload(
            material.id,
            length_bucket=digest_row.length_bucket,
            extracted_char_count=digest_row.extracted_char_count,
        ),
    )

    gap_job = await _maybe_enqueue_gap_suggest(ctx, project)
    await ctx.session.commit()
    if gap_job is not None and gap_job.state == "QUEUED":
        wake_jobs(gap_job)


@register(JobType.SEARCH)
async def search_sources(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await ctx.session.get(Project, ctx.project_id)
    if project is None:
        return
    payload = ctx.payload
    query = str(payload.get("query") or "").strip()
    if not query:
        raise JobFailure("search_query_missing", message_key="error.internal.unexpected")
    gap_id = _payload_uuid(payload.get("gapSuggestionId"))
    query_index = int(payload.get("queryIndex") or 0)

    # Project-level source cap is visible, never a silent omission (FR-2.19).
    existing_hashes = set(
        (
            await ctx.session.scalars(
                select(SourceItem.url_hash).where(
                    SourceItem.project_id == project.id,
                    SourceItem.origin == SourceOrigin.WEB.value,
                    SourceItem.url_hash.is_not(None),
                )
            )
        ).all()
    )
    remaining = max(0, ctx.settings.search_cap_per_project - len(existing_hashes))

    # Provider calls never run inside an open transaction.
    await ctx.session.commit()
    if remaining <= 0:
        outcome = SearchOutcome(outcome="ZERO_RESULTS", results=[], error_code="source_cap_reached")
    else:
        outcome = await ctx.search.search(query, remaining)
    result_count = len(outcome.results) if outcome.outcome == "RESULTS" else 0

    if outcome.outcome == "RESULTS":
        inserted = 0
        for item in outcome.results:
            if inserted >= remaining:
                break
            url_hash = parsers.url_hash(item.url)
            if url_hash in existing_hashes:
                continue
            exists = await ctx.session.scalar(
                select(SourceItem.id).where(
                    SourceItem.project_id == project.id,
                    SourceItem.origin == SourceOrigin.WEB.value,
                    SourceItem.url_hash == url_hash,
                )
            )
            if exists is not None:
                continue
            existing_hashes.add(url_hash)
            inserted += 1
            domain = item.domain or urlparse(item.url).hostname or ""
            source = SourceItem(
                id=new_id(),
                project_id=project.id,
                origin=SourceOrigin.WEB.value,
                source_type=SourceType.WEB_RESULT.value,
                title=item.title[:300],
                summary=item.summary[:1200],
                domain=domain,
                url_hash=url_hash,
                content_ref=None,
                material_id=None,
                gap_suggestion_id=gap_id,
                rank=item.rank,
            )
            ctx.session.add(source)
            await ctx.session.flush()
            await events.append(
                ctx.session, project.id, "sourceAdded", research_service.source_added_payload(source)
            )
        result_count = inserted

    progress = {
        "outcome": outcome.outcome,
        "resultCount": result_count,
        "errorCode": outcome.error_code,
    }
    ctx.job.progress = progress
    ctx.job.payload = {**payload, "resultCount": result_count}
    if gap_id is not None:
        completed: dict[str, Any] = {
            "gapSuggestionId": str(gap_id),
            "queryIndex": query_index,
            "outcome": outcome.outcome,
            "resultCount": result_count,
        }
        if outcome.error_code:
            completed["errorCode"] = outcome.error_code
        await events.append(ctx.session, project.id, "gapSearchCompleted", completed)

    await ctx.usage(
        capability="search",
        unit_type="query",
        quantity=1.0,
        provider=ctx.settings.search_provider,
    )
    await ctx.session.commit()


@register(JobType.GAP_SUGGEST)
async def suggest_gaps(ctx: JobContext) -> None:
    await ctx.check_cancel()
    project = await ctx.session.get(Project, ctx.project_id)
    if project is None:
        return
    if await research_service.latest_gap_batch(ctx.session, project) is not None:
        return

    summaries = await research_service.digest_summaries(ctx.session, project)
    answers = research_service.gap_answer_payload(
        await research_service.load_answers(ctx.session, project)
    )
    topic = project.topic
    # Read-only transaction is closed before the model call.
    await ctx.session.commit()
    result = await ctx.gateway.gaps(topic=topic, digests=summaries, answers=answers)
    suggestions = list(result.value.suggestions)
    if len(suggestions) < 3:
        raise JobFailure(
            "provider_invalid_output",
            category="provider_unavailable",
            message_key="error.provider.unavailable",
            retryable=True,
        )
    # Another worker may have produced the batch while the provider was busy.
    if await research_service.latest_gap_batch(ctx.session, project) is not None:
        return

    batch = int(await research_service.latest_gap_batch(ctx.session, project) or 0) + 1
    rows: list[GapSuggestion] = []
    for position, suggestion in enumerate(suggestions[:3], start=1):
        row = GapSuggestion(
            id=new_id(),
            project_id=project.id,
            batch=batch,
            label=str(suggestion.label),
            reason=str(suggestion.reason),
            recommended=bool(suggestion.recommended),
            position=position,
            status="SUGGESTED",
            producer_job_id=ctx.job.id,
        )
        ctx.session.add(row)
        rows.append(row)
    await ctx.session.flush()

    usage = result.usage
    await ctx.usage(
        capability="gaps",
        unit_type="tokens",
        quantity=float(usage.input_tokens + usage.output_tokens),
        provider=usage.provider,
        estimated_cost=usage.estimated_cost,
    )
    await events.append(
        ctx.session,
        project.id,
        "gapSuggested",
        {
            "batch": batch,
            "count": len(rows),
            "recommendedCount": sum(1 for row in rows if row.recommended),
            "suggestionIds": [str(row.id) for row in rows],
        },
    )
    await ctx.session.commit()
