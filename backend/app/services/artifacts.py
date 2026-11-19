"""Artifact commit, reuse-install, history and undo.

Commit protocol (backend design §8.2): content is written to object storage before
metadata, the pointer install is the commit point, and the displaced current version
is pushed onto the per-page/kind history stack. A retired page never receives a
pointer.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError, gate
from app.core.idempotency import bump_project
from app.core.ids import new_id, utcnow
from app.domain.enums import ArtifactKind
from app.domain.fingerprints import chrome_version
from app.models import (
    ArtifactLineage,
    ArtifactPointer,
    ArtifactSourceRef,
    ArtifactVersion,
    OutlinePageVersion,
    Page,
    PageHistoryEntry,
    Project,
    SourceItem,
)
from app.schemas.dto import (
    ArtifactChromeDTO,
    ArtifactDTO,
    ArtifactHistoryDTO,
    ArtifactSourceRefDTO,
    HistoryEntryDTO,
    PageHistoryDTO,
)
from app.services import state
from app.storage import storage


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def body_bytes(body: dict[str, Any]) -> bytes:
    return json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


async def write_body(storage_key: str, body: dict[str, Any]) -> tuple[str, str, int]:
    """Write a JSON artifact body; return (content_ref, sha256, byte_size)."""
    data = body_bytes(body)
    result = await _resolve(storage.put_bytes(storage_key, data, "application/json"))
    size = int(getattr(result, "size", len(data)) or len(data))
    return storage_key, hashlib.sha256(data).hexdigest(), size


async def read_artifact_body(version: ArtifactVersion) -> dict[str, Any]:
    try:
        raw = await _resolve(storage.get_bytes(version.content_ref))
    except Exception as exc:  # noqa: BLE001 - a pointer must never resolve to missing content
        raise AppError("internal", "error.internal.unexpected") from exc
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AppError("internal", "error.internal.unexpected") from exc
    if not isinstance(value, dict):
        raise AppError("internal", "error.internal.unexpected")
    return value


async def read_text_ref(storage_key: str) -> str:
    try:
        raw = await _resolve(storage.get_bytes(storage_key))
    except Exception as exc:  # noqa: BLE001
        raise AppError("internal", "error.internal.unexpected") from exc
    return raw.decode("utf-8", errors="replace")


async def write_text_ref(storage_key: str, text: str) -> str:
    await _resolve(storage.put_bytes(storage_key, text.encode("utf-8"), "text/plain"))
    return storage_key


def _artifact_key(project: Project, page: Page, kind: str, version: int) -> str:
    return f"projects/{project.id}/pages/{page.id}/{kind.lower()}/{version}.json"


async def _next_version(session: AsyncSession, project: Project, page_id: UUID, kind: str) -> int:
    current = await session.scalar(
        select(func.max(ArtifactVersion.version)).where(
            ArtifactVersion.project_id == project.id,
            ArtifactVersion.page_id == page_id,
            ArtifactVersion.kind == kind,
        )
    )
    return int(current or 0) + 1


async def _lock_pointer(
    session: AsyncSession, project: Project, page_id: UUID, kind: str
) -> ArtifactPointer | None:
    return await session.scalar(
        select(ArtifactPointer)
        .where(
            ArtifactPointer.project_id == project.id,
            ArtifactPointer.page_id == page_id,
            ArtifactPointer.kind == kind,
        )
        .with_for_update()
    )


async def _active_depth(session: AsyncSession, project: Project, page_id: UUID, kind: str) -> int:
    depth = await session.scalar(
        select(func.count())
        .select_from(PageHistoryEntry)
        .where(
            PageHistoryEntry.project_id == project.id,
            PageHistoryEntry.page_id == page_id,
            PageHistoryEntry.kind == kind,
            PageHistoryEntry.popped_at.is_(None),
        )
    )
    return int(depth or 0)


async def _push_history(
    session: AsyncSession,
    project: Project,
    page_id: UUID,
    kind: str,
    prior_version_id: UUID,
    reason: str,
) -> None:
    max_seq = await session.scalar(
        select(func.max(PageHistoryEntry.stack_sequence)).where(
            PageHistoryEntry.project_id == project.id,
            PageHistoryEntry.page_id == page_id,
            PageHistoryEntry.kind == kind,
            PageHistoryEntry.popped_at.is_(None),
        )
    )
    entry = PageHistoryEntry(
        id=new_id(),
        project_id=project.id,
        page_id=page_id,
        kind=kind,
        artifact_version_id=prior_version_id,
        stack_sequence=int(max_seq or 0) + 1,
        reason=reason,
        created_at=utcnow(),
    )
    session.add(entry)
    await session.flush()

    # Bound the active undo stack at PAGE_HISTORY_MAX_DEPTH by popping the oldest rows.
    max_depth = max(1, get_settings().page_history_max_depth)
    active = list(
        (
            await session.scalars(
                select(PageHistoryEntry)
                .where(
                    PageHistoryEntry.project_id == project.id,
                    PageHistoryEntry.page_id == page_id,
                    PageHistoryEntry.kind == kind,
                    PageHistoryEntry.popped_at.is_(None),
                )
                .order_by(PageHistoryEntry.stack_sequence.asc())
            )
        ).all()
    )
    overflow = len(active) - max_depth
    for row in active[: max(0, overflow)]:
        row.popped_at = utcnow()


async def _insert_lineage(
    session: AsyncSession, project: Project, version_id: UUID, upstream_refs: dict[str, Any] | None
) -> None:
    if not upstream_refs:
        return
    candidates = [
        ("planArtifactVersionId", "artifact_version", "plan"),
        ("outlineVersionId", "outline_version", "outline"),
        ("outlinePageVersionId", "outline_page_version", "outline_page"),
        ("styleDefinitionId", "style_definition", "style"),
        ("profileVersionId", "requirements_profile", "profile"),
    ]
    seen: set[tuple[str, str]] = set()
    for key, upstream_type, relation in candidates:
        raw = upstream_refs.get(key)
        if not raw:
            continue
        try:
            upstream_id = UUID(str(raw))
        except (ValueError, TypeError):
            continue
        if (upstream_type, str(upstream_id)) in seen:
            continue
        seen.add((upstream_type, str(upstream_id)))
        session.add(
            ArtifactLineage(
                id=new_id(),
                project_id=project.id,
                downstream_artifact_version_id=version_id,
                upstream_type=upstream_type,
                upstream_id=upstream_id,
                relation=relation,
                created_at=utcnow(),
            )
        )
    await session.flush()


async def _insert_source_refs(
    session: AsyncSession, project: Project, version_id: UUID, source_refs: list[UUID | str] | None
) -> None:
    if not source_refs:
        return
    ids: list[UUID] = []
    for raw in source_refs:
        try:
            ids.append(UUID(str(raw)))
        except (ValueError, TypeError):
            continue
    if not ids:
        return
    existing = set(
        (
            await session.scalars(
                select(SourceItem.id).where(SourceItem.project_id == project.id, SourceItem.id.in_(ids))
            )
        ).all()
    )
    for source_id in dict.fromkeys(ids):
        if source_id not in existing:
            continue
        session.add(
            ArtifactSourceRef(
                id=new_id(),
                project_id=project.id,
                artifact_version_id=version_id,
                source_item_id=source_id,
                role="supporting",
                created_at=utcnow(),
            )
        )
    await session.flush()


async def commit_artifact(
    session: AsyncSession,
    project: Project,
    page: Page,
    kind: str,
    body: dict[str, Any],
    fingerprint: str,
    source_refs: list[UUID | str] | None = None,
    *,
    producer_job_id: UUID | None = None,
    producer_attempt_id: UUID | None = None,
    producer_model: str | None = None,
    prompt_version: str | None = None,
    reason: str = "MANUAL",
    upstream_refs: dict[str, Any] | None = None,
    schema_version: int = 1,
) -> ArtifactVersion:
    """Commit an artifact version and install it as the page's current pointer.

    Raises when the page has been retired: a late job must never revive a page.
    """
    if page.retired_at is not None:
        raise AppError(
            "conflict",
            "error.conflict.stale_version",
            retryable=False,
            details={"reason": "page_retired"},
        )

    version_no = await _next_version(session, project, page.id, kind)
    content_ref, digest, size = await write_body(_artifact_key(project, page, kind, version_no), body)

    version = ArtifactVersion(
        id=new_id(),
        project_id=project.id,
        page_id=page.id,
        kind=kind,
        version=version_no,
        content_ref=content_ref,
        content_digest=digest,
        mime_type="application/json",
        byte_size=size,
        input_fingerprint=fingerprint,
        upstream_refs=dict(upstream_refs or {}),
        source_refs=[str(s) for s in (source_refs or [])],
        producer_job_id=producer_job_id,
        producer_attempt_id=producer_attempt_id,
        producer_model=producer_model,
        prompt_version=prompt_version,
        schema_version=schema_version,
        created_at=utcnow(),
    )
    session.add(version)
    await session.flush()

    await _insert_lineage(session, project, version.id, upstream_refs)
    await _insert_source_refs(session, project, version.id, source_refs)

    pointer = await _lock_pointer(session, project, page.id, kind)
    if pointer is not None and pointer.artifact_version_id != version.id:
        await _push_history(session, project, page.id, kind, pointer.artifact_version_id, reason)
        pointer.artifact_version_id = version.id
        pointer.updated_at = utcnow()
    elif pointer is None:
        session.add(
            ArtifactPointer(
                id=new_id(),
                project_id=project.id,
                page_id=page.id,
                kind=kind,
                artifact_version_id=version.id,
                updated_at=utcnow(),
            )
        )
    await session.flush()

    bump_project(project)
    return version


async def install_reused(
    session: AsyncSession,
    project: Project,
    page: Page,
    kind: str,
    existing_version: ArtifactVersion,
    reason: str = "MANUAL",
) -> ArtifactVersion:
    """Install an existing matching version by pointer with zero jobs.

    The caller owns the project-version bump for the enclosing command.
    """
    if page.retired_at is not None:
        raise AppError(
            "conflict", "error.conflict.stale_version", retryable=False, details={"reason": "page_retired"}
        )
    if (
        existing_version.project_id != project.id
        or existing_version.page_id != page.id
        or existing_version.kind != kind
    ):
        raise AppError("internal", "error.internal.unexpected")
    pointer = await _lock_pointer(session, project, page.id, kind)
    if pointer is not None and pointer.artifact_version_id == existing_version.id:
        return existing_version
    if pointer is not None:
        await _push_history(session, project, page.id, kind, pointer.artifact_version_id, reason)
        pointer.artifact_version_id = existing_version.id
        pointer.updated_at = utcnow()
    else:
        session.add(
            ArtifactPointer(
                id=new_id(),
                project_id=project.id,
                page_id=page.id,
                kind=kind,
                artifact_version_id=existing_version.id,
                updated_at=utcnow(),
            )
        )
    await session.flush()
    return existing_version


async def pointer_for(
    session: AsyncSession, project: Project, page_id: UUID, kind: str
) -> ArtifactPointer | None:
    return await session.scalar(
        select(ArtifactPointer).where(
            ArtifactPointer.project_id == project.id,
            ArtifactPointer.page_id == page_id,
            ArtifactPointer.kind == kind,
        )
    )


async def history_dto(
    session: AsyncSession, project: Project, page_id: UUID, kind: str, current_version_id: UUID | None
) -> PageHistoryDTO:
    depth = await _active_depth(session, project, page_id, kind)
    rows = list(
        (
            await session.scalars(
                select(PageHistoryEntry)
                .where(
                    PageHistoryEntry.project_id == project.id,
                    PageHistoryEntry.page_id == page_id,
                    PageHistoryEntry.kind == kind,
                )
                .order_by(PageHistoryEntry.stack_sequence.desc())
            )
        ).all()
    )
    versions: dict[UUID, int] = {}
    version_ids = {row.artifact_version_id for row in rows}
    if version_ids:
        found = (
            await session.scalars(
                select(ArtifactVersion).where(ArtifactVersion.id.in_(version_ids))
            )
        ).all()
        versions = {v.id: v.version for v in found}
    entries = [
        HistoryEntryDTO(
            artifact_version_id=row.artifact_version_id,
            version=versions.get(row.artifact_version_id, 0),
            reason=row.reason,
            created_at=row.created_at,
            is_current=row.artifact_version_id == current_version_id,
            undone=row.popped_at is not None,
        )
        for row in rows
    ]
    return PageHistoryDTO(
        page_id=page_id,
        kind=kind,
        depth=depth,
        can_undo=depth > 0,
        entries=entries,
    )


async def undo(
    session: AsyncSession, project: Project, page: Page, kind: str
) -> tuple[ArtifactVersion, ArtifactPointer]:
    """Pointer-only history restore. No model call, no new artifact, no job."""
    if kind not in {ArtifactKind.PLAN.value, ArtifactKind.DESIGN.value}:
        raise AppError("validation", "error.validation.invalid_request")
    if page.retired_at is not None:
        raise AppError("not_found", "error.not_found.artifact")
    pointer = await _lock_pointer(session, project, page.id, kind)
    if pointer is None:
        raise gate("error.gate.nothing_to_undo")
    top = await session.scalar(
        select(PageHistoryEntry)
        .where(
            PageHistoryEntry.project_id == project.id,
            PageHistoryEntry.page_id == page.id,
            PageHistoryEntry.kind == kind,
            PageHistoryEntry.popped_at.is_(None),
        )
        .order_by(PageHistoryEntry.stack_sequence.desc())
        .limit(1)
    )
    if top is None:
        raise gate("error.gate.nothing_to_undo")
    restored = await session.get(ArtifactVersion, top.artifact_version_id)
    if restored is None:
        raise gate("error.gate.nothing_to_undo")
    pointer.artifact_version_id = restored.id
    pointer.updated_at = utcnow()
    top.popped_at = utcnow()
    await session.flush()
    bump_project(project)
    return restored, pointer


def _chrome_for(
    page_row: OutlinePageVersion | None, bundle: state.OutlineBundle
) -> ArtifactChromeDTO:
    if page_row is None:
        raise AppError("not_found", "error.not_found.artifact")
    label = bundle.section_titles.get(page_row.section_key)
    return ArtifactChromeDTO(
        page_number=page_row.position,
        deck_order=page_row.position,
        title=page_row.title,
        section_label=label,
        chrome_version=chrome_version(
            page_id=str(page_row.page_id),
            title=page_row.title,
            position=page_row.position,
            deck_order=page_row.position,
            section_key=page_row.section_key,
            section_label=label,
        ),
    )


async def build_artifact_dto(
    session: AsyncSession, project: Project, page_id: UUID, kind: str
) -> ArtifactDTO:
    if kind not in {ArtifactKind.PLAN.value, ArtifactKind.DESIGN.value}:
        raise AppError("validation", "error.validation.invalid_request")
    bundle = await state.load_outline(session, project)
    page_row = bundle.by_page.get(page_id)
    if page_row is None:
        raise AppError("not_found", "error.not_found.artifact")
    page = await session.get(Page, page_id)
    if page is None or page.retired_at is not None:
        raise AppError("not_found", "error.not_found.artifact")
    pointer = await pointer_for(session, project, page_id, kind)
    if pointer is None:
        raise AppError("not_found", "error.not_found.artifact")
    version = await session.get(ArtifactVersion, pointer.artifact_version_id)
    if version is None:
        raise AppError("not_found", "error.not_found.artifact")
    body = await read_artifact_body(version)
    chrome = _chrome_for(page_row, bundle)

    ref_rows = (
        await session.execute(
            select(ArtifactSourceRef, SourceItem)
            .join(SourceItem, SourceItem.id == ArtifactSourceRef.source_item_id)
            .where(ArtifactSourceRef.artifact_version_id == version.id)
        )
    ).all()
    source_refs = [
        ArtifactSourceRefDTO(
            source_item_id=item.id,
            title=item.title,
            origin=item.origin,
            role=ref.role,
        )
        for ref, item in ref_rows
    ]

    page_list = await state.build_page_list(session, project)
    summary = next((p for p in page_list.pages if p.page_id == page_id), None)
    if summary is not None:
        status = summary.plan.status if kind == ArtifactKind.PLAN.value else summary.design.status
    else:
        status = "DONE"
    depth = await _active_depth(session, project, page_id, kind)
    return ArtifactDTO(
        artifact_version_id=version.id,
        page_id=page_id,
        kind=kind,
        version=version.version,
        content_digest=version.content_digest,
        input_fingerprint=version.input_fingerprint,
        schema_version=version.schema_version,
        body=body,
        chrome=chrome,
        source_refs=source_refs,
        history=ArtifactHistoryDTO(
            depth=depth,
            can_undo=depth > 0,
            current_pointer_version=version.version,
        ),
        status=status,
        created_at=version.created_at or datetime.min,
    )
