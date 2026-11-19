"""Shared generation helpers: model inputs, body normalization, reuse and staleness.

The pure fingerprint functions live in `app.domain.fingerprints`; this module only
assembles their inputs from persisted rows and repairs model output against the
shared layout vocabulary.
"""

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, gate
from app.domain import layouts as layout_domain
from app.domain.enums import ArtifactKind, JobType, PageStatus, PageType, Stage
from app.domain.fingerprints import chrome_version, design_fingerprint, plan_fingerprint
from app.models import (
    ArtifactVersion,
    InterviewAnswer,
    InterviewQuestion,
    MaterialDigest,
    OutlinePageVersion,
    Page,
    Project,
    RequirementsProfile,
    SourceItem,
    StyleDefinition,
    StyleSelection,
)
from app.schemas.dto import (
    OutlineCountsDTO,
    OutlineDTO,
    OutlinePageDTO,
    OutlineSectionDTO,
)
from app.services import state
from app.storage import storage

CANVAS = {"width": 1280, "height": 720}


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _get(obj: Any, *names: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        for name in names:
            if name in obj and obj[name] is not None:
                return obj[name]
        return default
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def slug(value: str, *, fallback: str = "section") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip().lower()).strip("-_")
    return cleaned or fallback


# ---- Model inputs ----------------------------------------------------------


def profile_payload(profile: RequirementsProfile) -> dict[str, Any]:
    return {
        "audience": profile.audience,
        "goal": profile.goal,
        "styleMood": profile.style_mood,
        "pageCount": profile.page_count,
        "contentStrategy": profile.content_strategy,
    }


async def load_answers(session: AsyncSession, project: Project) -> dict[str, str]:
    rows = (
        await session.execute(
            select(InterviewQuestion.question_key, InterviewAnswer.option_key)
            .join(InterviewAnswer, InterviewAnswer.question_id == InterviewQuestion.id)
            .where(InterviewQuestion.project_id == project.id)
        )
    ).all()
    return {key: option for key, option in rows}


async def load_digests_payload(session: AsyncSession, project: Project) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(MaterialDigest)
                .where(MaterialDigest.project_id == project.id, MaterialDigest.is_current.is_(True))
                .order_by(MaterialDigest.created_at)
            )
        ).all()
    )
    payload: list[dict[str, Any]] = []
    for digest in rows:
        item: dict[str, Any] = {
            "materialId": str(digest.material_id),
            "summary": digest.summary_preview or "",
            "keyFacts": [],
            "lengthBucket": digest.length_bucket or "medium",
        }
        if digest.digest_ref:
            try:
                raw = await _resolve(storage.get_bytes(digest.digest_ref))
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict):
                    item["summary"] = str(data.get("summary") or item["summary"])
                    facts = data.get("key_facts") or data.get("keyFacts") or []
                    item["keyFacts"] = [str(f) for f in facts][:6]
                    item["lengthBucket"] = str(data.get("length_bucket") or item["lengthBucket"])
            except Exception:  # noqa: BLE001 - a missing digest never blocks the outline
                pass
        payload.append(item)
    return payload


async def load_sources_payload(session: AsyncSession, project: Project, limit: int = 14) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(SourceItem)
                .where(SourceItem.project_id == project.id)
                .order_by(SourceItem.origin, SourceItem.rank, SourceItem.created_at)
                .limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "origin": row.origin,
            "sourceType": row.source_type,
            "title": row.title,
            "summary": row.summary,
            "domain": row.domain,
        }
        for row in rows
    ]


# ---- Fingerprints ----------------------------------------------------------


def expected_plan_fingerprint(project: Project, page: OutlinePageVersion) -> str:
    return plan_fingerprint(
        project_id=str(project.id),
        page_id=str(page.page_id),
        page_type=page.page_type,
        section_key=page.section_key,
        key_points=list(page.key_points or []),
    )


def expected_design_fingerprint(
    project: Project,
    page: OutlinePageVersion,
    plan_version: ArtifactVersion,
    style: StyleSelection,
    style_def: StyleDefinition,
) -> str:
    return design_fingerprint(
        project_id=str(project.id),
        page_id=str(page.page_id),
        plan_artifact_version_id=str(plan_version.id),
        style_definition_id=str(style_def.id),
        style_version=style.style_version,
    )


async def find_reusable_version(
    session: AsyncSession, project: Project, page_id: UUID, kind: str, fingerprint: str
) -> ArtifactVersion | None:
    return await session.scalar(
        select(ArtifactVersion)
        .where(
            ArtifactVersion.project_id == project.id,
            ArtifactVersion.page_id == page_id,
            ArtifactVersion.kind == kind,
            ArtifactVersion.input_fingerprint == fingerprint,
        )
        .order_by(ArtifactVersion.created_at.desc())
        .limit(1)
    )


async def design_stale_pages(session: AsyncSession, project: Project) -> list[UUID]:
    page_list = await state.build_page_list(session, project)
    return [p.page_id for p in page_list.pages if p.design.status == PageStatus.STALE.value]


# ---- Body normalization ----------------------------------------------------


def known_layout_id(layout_id: str | None, page_type: str, position: int) -> str:
    if layout_id and layout_id in layout_domain.layouts()["layouts"]:
        return layout_id
    return layout_domain.layout_for_page(page_type, position)


def _slot_keys(layout_id: str) -> tuple[set[str], str, dict[str, list[str]]]:
    spec = layout_domain.layout(layout_id)
    slots = spec["slots"]
    keys = {slot["key"] for slot in slots}
    first = slots[0]["key"]
    roles = {slot["key"]: list(slot.get("roles") or []) for slot in slots}
    return keys, first, roles


def _normalize_blocks(raw_blocks: Any, *, design: bool, layout_id: str, style_tokens: dict[str, Any] | None) -> list[dict[str, Any]]:
    keys, first_slot, roles_by_slot = _slot_keys(layout_id)
    blocks: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_blocks or []):
        if not isinstance(raw, dict):
            continue
        slot = str(_get(raw, "slot", default=first_slot))
        if slot not in keys:
            slot = first_slot
        role = str(_get(raw, "role", default="body") or "body")
        allowed_roles = roles_by_slot.get(slot) or []
        if allowed_roles and role not in allowed_roles:
            # The layout vocabulary is authoritative; fall back to the slot's first role.
            role = allowed_roles[0]
        items = _get(raw, "items")
        block: dict[str, Any] = {
            "id": str(_get(raw, "id", default=f"b{index + 1}") or f"b{index + 1}"),
            "slot": slot,
            "role": role,
        }
        text = _get(raw, "text")
        if text is not None:
            block["text"] = str(text)
        if items is not None:
            block["items"] = [str(item) for item in items]
        asset_ref = _get(raw, "asset_ref", "assetRef")
        if asset_ref:
            block["assetRef"] = str(asset_ref)
        emphasis = _get(raw, "emphasis")
        if emphasis:
            block["emphasis"] = str(emphasis)
        span = _get(raw, "span")
        if isinstance(span, dict):
            block["span"] = span
        if design:
            style_raw = _get(raw, "style", default={}) or {}
            text_style = str(_get(style_raw, "text_style", "textStyle", default=role) or role)
            color_role = str(_get(style_raw, "color_role", "colorRole", default="text") or "text")
            spec = (style_tokens or {}).get("textStyles", {}).get(text_style)
            if isinstance(spec, dict) and spec.get("colorRole"):
                color_role = str(spec["colorRole"])
            align = _get(style_raw, "align")
            block["style"] = {
                "textStyle": text_style,
                "colorRole": color_role,
                "align": align if align in {"left", "center", "right"} else "left",
            }
        blocks.append(block)

    if not blocks:
        fallback_role = "headline" if (not roles_by_slot.get(first_slot) or "headline" in roles_by_slot[first_slot]) else (
            roles_by_slot.get(first_slot) or ["body"]
        )[0]
        block = {"id": "b1", "slot": first_slot, "role": fallback_role, "text": ""}
        if design:
            block["style"] = {"textStyle": fallback_role, "colorRole": "text", "align": "left"}
        blocks = [block]
    return blocks


def _key_points_used(raw_meta: Any) -> list[str]:
    if not isinstance(raw_meta, dict):
        return []
    used = _get(raw_meta, "key_points_used", "keyPointsUsed", default=[])
    return [str(item) for item in used] if isinstance(used, list) else []


def normalize_plan_body(raw: Any, *, title: str, page_type: str, position: int) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    layout_id = known_layout_id(str(_get(data, "layout_id", "layoutId", default="") or ""), page_type, position)
    density = str(_get(data, "density", default="medium") or "medium")
    if density not in {"low", "medium", "high"}:
        density = "medium"
    meta = _get(data, "meta", default={}) or {}
    body = {
        "schemaVersion": 1,
        "canvas": dict(CANVAS),
        "layoutId": layout_id,
        "density": density,
        "blocks": _normalize_blocks(_get(data, "blocks", default=[]), design=False, layout_id=layout_id, style_tokens=None),
        "meta": {
            "title": title,
            "keyPointsUsed": _key_points_used(meta),
        },
    }
    return body


def normalize_design_body(
    raw: Any,
    *,
    title: str,
    page_type: str,
    position: int,
    style_key: str,
    style_version: int,
    theme_data: dict[str, Any],
) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    layout_id = known_layout_id(str(_get(data, "layout_id", "layoutId", default="") or ""), page_type, position)
    density = str(_get(data, "density", default="medium") or "medium")
    if density not in {"low", "medium", "high"}:
        density = "medium"
    style_raw = _get(data, "style", default={}) or {}
    tokens_raw = _get(style_raw, "tokens", default={}) or {}
    tokens = {k: v for k, v in dict(tokens_raw).items() if isinstance(v, (str, int, float))}
    palette = theme_data.get("palette", {})
    for key, value in palette.items():
        tokens.setdefault(key, value)
    assets: list[dict[str, Any]] = []
    for raw_asset in _get(data, "assets", default=[]) or []:
        if not isinstance(raw_asset, dict):
            continue
        asset_id = _get(raw_asset, "asset_id", "assetId")
        if not asset_id:
            continue
        assets.append(
            {
                "assetId": str(asset_id),
                "kind": str(_get(raw_asset, "kind", default="image") or "image"),
                "width": int(_get(raw_asset, "width", default=0) or 0),
                "height": int(_get(raw_asset, "height", default=0) or 0),
                "licenseStatus": str(_get(raw_asset, "license_status", "licenseStatus", default="UNKNOWN")),
            }
        )
    meta = _get(data, "meta", default={}) or {}
    return {
        "schemaVersion": 1,
        "canvas": dict(CANVAS),
        "layoutId": layout_id,
        "density": density,
        "style": {
            "styleKey": style_key,
            "styleVersion": style_version,
            "tokens": tokens,
        },
        "blocks": _normalize_blocks(
            _get(data, "blocks", default=[]), design=True, layout_id=layout_id, style_tokens=theme_data
        ),
        "assets": assets,
        "meta": {"title": title, **{k: v for k, v in dict(meta).items() if k != "title"}},
    }


# ---- Rendering theme -------------------------------------------------------


def theme_for_key(style_key: str) -> dict[str, Any]:
    themes = layout_domain.themes()
    if style_key in themes:
        return themes[style_key]
    raise AppError("gate_violation", "error.validation.unknown_style", details={"reason": "style_missing"})


def visible_text(body: dict[str, Any]) -> str:
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


def page_kind(kind: str) -> str:
    return ArtifactKind.PLAN.value if kind.upper() == "PLAN" else ArtifactKind.DESIGN.value


def is_fixed_page(page_type: str) -> bool:
    return page_type in {PageType.COVER.value, PageType.TOC.value, PageType.END.value}


# ---- Route/handler helpers -------------------------------------------------


def body_to_dict(raw: Any) -> dict[str, Any]:
    """Coerce a model result (dict or pydantic model) into a plain mapping."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        try:
            value = dump(by_alias=True, exclude_none=True)
        except TypeError:
            value = dump()
        return dict(value) if isinstance(value, dict) else {}
    return {}


def _block_for_model(block: dict[str, Any]) -> dict[str, Any]:
    value = dict(block)
    if "assetRef" in value:
        value["asset_ref"] = value.pop("assetRef")
    if "asset_ref" in value and value.get("asset_ref") is None:
        value.pop("asset_ref", None)
    return value


def plan_for_model(body: dict[str, Any]) -> dict[str, Any]:
    """Re-shape a stored canonical plan body into the gateway's PlanBodyV1 keys."""
    return {
        "schema_version": int(body.get("schemaVersion") or 1),
        "canvas": dict(body.get("canvas") or CANVAS),
        "layout_id": str(body.get("layoutId") or body.get("layout_id") or "single"),
        "density": str(body.get("density") or "medium"),
        "blocks": [_block_for_model(b) for b in body.get("blocks") or [] if isinstance(b, dict)],
        "meta": dict(body.get("meta") or {}),
    }


def design_for_model(body: dict[str, Any]) -> dict[str, Any]:
    """Re-shape a stored canonical design body into the gateway's DesignBodyV1 keys."""
    style = body.get("style") if isinstance(body.get("style"), dict) else {}
    assets = []
    for asset in body.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        assets.append(
            {
                "asset_id": str(asset.get("assetId") or asset.get("asset_id") or ""),
                "kind": str(asset.get("kind") or "image"),
                "width": int(asset.get("width") or 0),
                "height": int(asset.get("height") or 0),
                "license_status": str(asset.get("licenseStatus") or asset.get("license_status") or "UNKNOWN"),
            }
        )
    return {
        "schema_version": int(body.get("schemaVersion") or 1),
        "canvas": dict(body.get("canvas") or CANVAS),
        "layout_id": str(body.get("layoutId") or body.get("layout_id") or "single"),
        "density": str(body.get("density") or "medium"),
        "style": {
            "style_key": str(style.get("styleKey") or style.get("style_key") or ""),
            "style_version": int(style.get("styleVersion") or style.get("style_version") or 1),
            "tokens": dict(style.get("tokens") or {}),
        },
        "blocks": [_block_for_model(b) for b in body.get("blocks") or [] if isinstance(b, dict)],
        "assets": assets,
        "meta": dict(body.get("meta") or {}),
    }


def page_chrome(page_row: OutlinePageVersion, bundle: state.OutlineBundle) -> tuple[str, str | None]:
    label = bundle.section_titles.get(page_row.section_key)
    return (
        chrome_version(
            page_id=str(page_row.page_id),
            title=page_row.title,
            position=page_row.position,
            deck_order=page_row.position,
            section_key=page_row.section_key,
            section_label=label,
        ),
        label,
    )


async def build_outline_dto(
    session: AsyncSession, project: Project, *, stage_status: str | None = None
) -> OutlineDTO:
    bundle = await state.load_outline(session, project)
    if bundle.version is None:
        raise AppError("not_found", "error.not_found.outline")
    profile = await state.load_profile(session, project)
    agreed = int(profile.page_count) if profile is not None else 0
    body_pages = sum(1 for page in bundle.pages if page.page_type == PageType.BODY.value)
    deviation = len(bundle.pages) - agreed
    if stage_status is None:
        snapshot = await state.build_snapshot(session, project)
        stage_status = next(
            (item.status for item in snapshot.stages if item.stage == Stage.OUTLINE.value), "AVAILABLE"
        )
    return OutlineDTO(
        outline_version_id=bundle.version.id,
        version=bundle.version.version,
        confirmed=bool(bundle.version.confirmed_at),
        confirmed_at=bundle.version.confirmed_at,
        pages=[
            OutlinePageDTO(
                page_id=page.page_id,
                position=page.position,
                page_type=page.page_type,
                section_key=page.section_key,
                title=page.title,
                key_points=list(page.key_points or []),
                deletable=page.page_type == PageType.BODY.value,
            )
            for page in bundle.pages
        ],
        sections=[
            OutlineSectionDTO(section_key=s.section_key, title=s.title, position=s.position)
            for s in bundle.sections
        ],
        counts=OutlineCountsDTO(
            pages=len(bundle.pages),
            sections=len(bundle.sections),
            body_pages=body_pages,
            agreed_page_count=agreed,
            deviation=deviation,
            deviation_warning=abs(deviation) > 2,
        ),
        stage_status=stage_status,
    )


async def next_variant(session: AsyncSession, project: Project, page_id: UUID, kind: str) -> int:
    current = await session.scalar(
        select(func.max(ArtifactVersion.version)).where(
            ArtifactVersion.project_id == project.id,
            ArtifactVersion.page_id == page_id,
            ArtifactVersion.kind == kind,
        )
    )
    return int(current or 0)


@dataclass
class FanoutResult:
    jobs: list[dict[str, Any]] = field(default_factory=list)
    skipped_page_ids: list[UUID] = field(default_factory=list)
    required: int = 0
    job_rows: list[Any] = field(default_factory=list)


async def fan_out_pages(
    session: AsyncSession,
    project: Project,
    kind: str,
    *,
    reason: str = "REGENERATE",
    page_ids: list[UUID] | None = None,
) -> FanoutResult:
    """Reuse matching artifacts by pointer, then enqueue one job per remaining page."""
    from app.services import artifacts
    from app.services import jobs as job_service

    normalized = ArtifactKind.PLAN.value if kind.upper() == ArtifactKind.PLAN.value else ArtifactKind.DESIGN.value
    bundle = await state.load_outline(session, project)
    wanted = set(page_ids) if page_ids else None
    selected = [page for page in bundle.pages if wanted is None or page.page_id in wanted]
    result = FanoutResult(required=len(selected))

    selection: StyleSelection | None = None
    definition: StyleDefinition | None = None
    if normalized == ArtifactKind.DESIGN.value:
        selection, definition = await state.load_style_selection(session, project)
        if selection is None:
            raise gate("error.gate.style_not_selected")
        if not selection.confirmed_at:
            raise gate("error.gate.style_unconfirmed")
        if definition is None:
            raise gate("error.gate.style_not_selected")

    for page in selected:
        page_row = await session.get(Page, page.page_id)
        if page_row is None or page_row.retired_at is not None:
            continue
        if normalized == ArtifactKind.PLAN.value:
            fingerprint = expected_plan_fingerprint(project, page)
        else:
            plan_pointer = await artifacts.pointer_for(session, project, page.page_id, ArtifactKind.PLAN.value)
            plan_version = (
                await session.get(ArtifactVersion, plan_pointer.artifact_version_id)
                if plan_pointer is not None
                else None
            )
            if plan_version is None:
                raise gate("error.gate.plan_incomplete", {"pageId": str(page.page_id)})
            assert selection is not None and definition is not None
            fingerprint = expected_design_fingerprint(project, page, plan_version, selection, definition)

        reusable = await find_reusable_version(session, project, page.page_id, normalized, fingerprint)
        if reusable is not None:
            await artifacts.install_reused(session, project, page_row, normalized, reusable, reason="MANUAL")
            result.skipped_page_ids.append(page.page_id)
            continue

        job_type = JobType.PLAN_PAGE.value if normalized == ArtifactKind.PLAN.value else JobType.DESIGN_PAGE.value
        active = await job_service.find_active(session, f"page:{page.page_id}")
        if active is not None:
            if active.type != job_type:
                raise gate("error.gate.page_write_in_progress", {"pageId": str(page.page_id)})
            result.jobs.append({"pageId": page.page_id, "jobId": active.id})
            result.job_rows.append(active)
            continue
        job = await job_service.enqueue_job(
            session,
            project,
            job_type,
            operation_key=f"{normalized.lower()}:{page.page_id}:{project.version}",
            active_operation_key=f"page:{page.page_id}",
            payload={"pageId": str(page.page_id), "kind": normalized, "reason": reason},
        )
        result.jobs.append({"pageId": page.page_id, "jobId": job.id})
        result.job_rows.append(job)
    return result


async def enqueue_page_job(
    session: AsyncSession,
    project: Project,
    page_id: UUID,
    kind: str,
    *,
    reason: str = "REGENERATE",
    instruction: str | None = None,
) -> Any:
    """Gate and enqueue a single-page PLAN/DESIGN job (regenerate or tweak)."""
    from app.services import artifacts
    from app.services import jobs as job_service

    normalized = ArtifactKind.PLAN.value if kind.upper() == ArtifactKind.PLAN.value else ArtifactKind.DESIGN.value
    bundle = await state.load_outline(session, project)
    page = bundle.by_page.get(page_id)
    if bundle.version is None or page is None:
        raise AppError("not_found", "error.not_found.outline")
    page_row = await session.get(Page, page_id)
    if page_row is None or page_row.retired_at is not None:
        raise AppError("not_found", "error.not_found.artifact")

    active = await job_service.find_active(session, f"page:{page_id}")
    if active is not None:
        raise gate("error.gate.page_write_in_progress", {"pageId": str(page_id)})

    if normalized == ArtifactKind.DESIGN.value:
        selection, definition = await state.load_style_selection(session, project)
        if selection is None or definition is None:
            raise gate("error.gate.style_not_selected")
        if not selection.confirmed_at:
            raise gate("error.gate.style_unconfirmed")
        plan_pointer = await artifacts.pointer_for(session, project, page_id, ArtifactKind.PLAN.value)
        if plan_pointer is None:
            raise gate("error.gate.plan_incomplete", {"pageId": str(page_id)})
        if reason != "TWEAK" and is_fixed_page(page.page_type):
            raise gate("error.gate.single_layout_use_tweak", {"pageId": str(page_id)})
        if reason != "TWEAK":
            plan_version = await session.get(ArtifactVersion, plan_pointer.artifact_version_id)
            if plan_version is not None:
                plan_body = await artifacts.read_artifact_body(plan_version)
                if plan_body.get("layoutId") == "single":
                    raise gate("error.gate.single_layout_use_tweak", {"pageId": str(page_id)})

    job = await job_service.enqueue_job(
        session,
        project,
        JobType.DESIGN_PAGE.value if normalized == ArtifactKind.DESIGN.value else JobType.PLAN_PAGE.value,
        operation_key=f"{normalized.lower()}:{page_id}:{project.version}:{reason.lower()}",
        active_operation_key=f"page:{page_id}",
        payload={"pageId": str(page_id), "kind": normalized, "reason": reason},
    )
    if instruction is not None:
        key = f"projects/{project.id}/instructions/{job.id}.txt"
        await artifacts.write_text_ref(key, instruction)
        job.instruction_ref = key
        await session.flush()
    return job
