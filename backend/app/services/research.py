"""Research read model and domain helpers for M1.

All builders are server-authoritative: they read current rows and never accept
client-supplied content for projections. Content-bearing fields (prompts,
labels, summaries) are only returned from authorized queries, never events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import gate
from app.domain.enums import GapStatus, JobState, JobType, MaterialStatus, Stage
from app.domain.fingerprints import profile_fingerprint
from app.models import (
    GapDecision,
    GapSuggestion,
    InterviewAnswer,
    InterviewQuestion,
    Job,
    Material,
    MaterialDigest,
    Project,
    RequirementsProfile,
    SourceItem,
)
from app.schemas.dto import (
    ActiveJobRef,
    AnswerDTO,
    DigestStateDTO,
    GapDecisionDTO,
    GapSearchOutcomeDTO,
    GapStateDTO,
    GapSuggestionDTO,
    MaterialDigestDTO,
    MaterialsSummaryDTO,
    ProfileDTO,
    QuestionDTO,
    QuestionOptionDTO,
    ResearchCountsDTO,
    ResearchStateDTO,
    SourceGroupDTO,
    SourceItemDTO,
    SourcePanelDTO,
    WebScopeDTO,
    WebSourceGroupDTO,
)
from app.services.state import build_snapshot, compute_profile_dirty, load_profile

# Stable question catalog for M1. Version comes from configuration so a
# catalog change can invalidate stored snapshots deliberately.
QUESTION_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "key": "audience",
        "prompt": "Who is this deck mainly for?",
        "options": [
            {"key": "prospects", "label": "Prospects and partners"},
            {"key": "investors", "label": "Investors"},
            {"key": "internal", "label": "Internal management"},
            {"key": "public", "label": "Public conference audience"},
        ],
    },
    {
        "key": "goal",
        "prompt": "What outcome do you want?",
        "options": [
            {"key": "promote", "label": "Product promotion and trial conversion"},
            {"key": "brand", "label": "Brand and trust building"},
            {"key": "fundraise", "label": "Fundraising roadshow"},
            {"key": "report", "label": "Reporting and alignment"},
        ],
    },
    {
        "key": "style",
        "prompt": "Preferred style and mood?",
        "options": [
            {"key": "tech", "label": "Techy · dark and bold"},
            {"key": "business", "label": "Business professional · steady"},
            {"key": "warm", "label": "Warm and approachable · magazine"},
            {"key": "minimal", "label": "Minimal · black and white"},
        ],
    },
    {
        "key": "length",
        "prompt": "What page count do you expect?",
        "options": [
            {"key": "short", "label": "Around 7 pages"},
            {"key": "medium", "label": "Around 10 pages"},
            {"key": "long", "label": "Around 14 pages"},
        ],
    },
)

RESEARCH_JOB_TYPES = (
    JobType.INGEST.value,
    JobType.DIGEST.value,
    JobType.SEARCH.value,
    JobType.GAP_SUGGEST.value,
    JobType.PROFILE.value,
)
ACTIVE_JOB_STATES = (JobState.QUEUED.value, JobState.RUNNING.value)


@dataclass
class GapContext:
    batch: int | None = None
    suggestions: list[GapSuggestion] = field(default_factory=list)
    decisions: list[GapDecision] = field(default_factory=list)
    selected_ids: list[UUID] = field(default_factory=list)
    decided_at: datetime | None = None
    web_skipped: bool = False

    @property
    def decided(self) -> bool:
        return bool(self.suggestions) and len(self.decisions) >= len(self.suggestions)

    @property
    def all_selected(self) -> list[UUID]:
        return list(self.selected_ids)


@dataclass
class ProfileInputs:
    questions: list[InterviewQuestion]
    answers: dict[str, InterviewAnswer]
    answer_payload: dict[str, dict[str, str]]
    materials: list[Material]
    digests: list[dict[str, Any]]
    sources: list[SourceItem]
    gap: GapContext
    selected_gap_ids: list[UUID]
    web_skipped: bool
    fingerprint: str


def option_keys(question: InterviewQuestion | dict[str, Any]) -> list[str]:
    raw = question.options if isinstance(question, InterviewQuestion) else question.get("options", [])
    keys: list[str] = []
    for option in raw or []:
        if isinstance(option, dict) and option.get("key"):
            keys.append(str(option["key"]))
    return keys


def option_label(question: InterviewQuestion, key: str) -> str:
    for option in question.options or []:
        if isinstance(option, dict) and str(option.get("key")) == key:
            return str(option.get("label") or key)
    return key


async def load_questions(session: AsyncSession, project: Project) -> list[InterviewQuestion]:
    return list(
        (
            await session.scalars(
                select(InterviewQuestion)
                .where(InterviewQuestion.project_id == project.id)
                .order_by(InterviewQuestion.position)
            )
        ).all()
    )


async def ensure_questions(
    session: AsyncSession, project: Project
) -> tuple[list[InterviewQuestion], list[InterviewQuestion]]:
    """Create any missing catalog rows. Returns (all rows in position order, created)."""
    settings = get_settings()
    existing = list(
        (
            await session.scalars(
                select(InterviewQuestion)
                .where(InterviewQuestion.project_id == project.id)
                .order_by(InterviewQuestion.position)
            )
        ).all()
    )
    by_key = {q.question_key: q for q in existing}
    created: list[InterviewQuestion] = []
    for position, spec in enumerate(QUESTION_CATALOG, start=1):
        key = str(spec["key"])
        if key in by_key:
            continue
        row = InterviewQuestion(
            project_id=project.id,
            question_key=key,
            position=position,
            prompt=str(spec["prompt"]),
            options=list(spec["options"]),
            catalog_version=settings.question_catalog_version,
        )
        session.add(row)
        created.append(row)
        by_key[key] = row
    if created:
        await session.flush()
    rows = list(
        (
            await session.scalars(
                select(InterviewQuestion)
                .where(InterviewQuestion.project_id == project.id)
                .order_by(InterviewQuestion.position)
            )
        ).all()
    )
    return rows, created


async def load_answers(session: AsyncSession, project: Project) -> dict[str, InterviewAnswer]:
    rows = list(
        (
            await session.execute(
                select(InterviewQuestion.question_key, InterviewAnswer)
                .join(InterviewAnswer, InterviewAnswer.question_id == InterviewQuestion.id)
                .where(InterviewQuestion.project_id == project.id)
            )
        ).all()
    )
    return {str(key): answer for key, answer in rows}


def build_question_dtos(
    questions: list[InterviewQuestion], answers: dict[str, InterviewAnswer]
) -> list[QuestionDTO]:
    result: list[QuestionDTO] = []
    for question in questions:
        answer = answers.get(question.question_key)
        result.append(
            QuestionDTO(
                key=question.question_key,
                position=question.position,
                prompt=question.prompt,
                options=[
                    QuestionOptionDTO(key=str(o["key"]), label=str(o.get("label") or o["key"]))
                    for o in (question.options or [])
                    if isinstance(o, dict) and o.get("key")
                ],
                answer=(
                    AnswerDTO(
                        option_key=answer.option_key,
                        revision=answer.revision,
                        answered_at=answer.updated_at,
                    )
                    if answer
                    else None
                ),
            )
        )
    return result


async def latest_gap_batch(session: AsyncSession, project: Project) -> int | None:
    value = await session.scalar(
        select(func.max(GapSuggestion.batch)).where(GapSuggestion.project_id == project.id)
    )
    return int(value) if value is not None else None


async def load_gap_context(session: AsyncSession, project: Project) -> GapContext:
    batch = await latest_gap_batch(session, project)
    if batch is None:
        return GapContext()
    suggestions = list(
        (
            await session.scalars(
                select(GapSuggestion)
                .where(GapSuggestion.project_id == project.id, GapSuggestion.batch == batch)
                .order_by(GapSuggestion.position)
            )
        ).all()
    )
    decisions = list(
        (
            await session.scalars(
                select(GapDecision)
                .join(GapSuggestion, GapSuggestion.id == GapDecision.gap_suggestion_id)
                .where(GapSuggestion.project_id == project.id, GapSuggestion.batch == batch)
                .order_by(GapDecision.decided_at)
            )
        ).all()
    )
    selected = [d.gap_suggestion_id for d in decisions if d.selected]
    decided_at = max((d.decided_at for d in decisions), default=None)
    decided = bool(suggestions) and len(decisions) >= len(suggestions)
    return GapContext(
        batch=batch,
        suggestions=suggestions,
        decisions=decisions,
        selected_ids=selected,
        decided_at=decided_at,
        web_skipped=decided and not selected,
    )


def gap_suggestion_dto(row: GapSuggestion) -> GapSuggestionDTO:
    return GapSuggestionDTO(
        id=row.id,
        label=row.label,
        reason=row.reason,
        recommended=bool(row.recommended),
        status=row.status,
    )


def gap_state_dto(gap: GapContext) -> GapStateDTO | None:
    if gap.batch is None:
        return None
    decision = None
    if gap.decided and gap.decided_at is not None:
        decision = GapDecisionDTO(
            decided_at=gap.decided_at,
            selected_suggestion_ids=list(gap.selected_ids),
            web_skipped=gap.web_skipped,
        )
    return GapStateDTO(
        batch=gap.batch,
        suggestions=[gap_suggestion_dto(s) for s in gap.suggestions],
        decision=decision,
    )


async def selected_gap_ids_all(session: AsyncSession, project: Project) -> list[UUID]:
    rows = (
        await session.execute(
            select(GapSuggestion.id)
            .join(GapDecision, GapDecision.gap_suggestion_id == GapSuggestion.id)
            .where(GapSuggestion.project_id == project.id, GapDecision.selected.is_(True))
        )
    ).all()
    return [row[0] for row in rows]


async def build_gap_searches(
    session: AsyncSession, project: Project, gap: GapContext | None = None
) -> list[GapSearchOutcomeDTO]:
    gap = gap or await load_gap_context(session, project)
    if not gap.suggestions or not gap.decided:
        return []
    selected = set(gap.selected_ids)
    if not selected:
        return []
    jobs = list(
        (
            await session.scalars(
                select(Job)
                .where(Job.project_id == project.id, Job.type == JobType.SEARCH.value)
                .order_by(Job.created_at.desc())
            )
        ).all()
    )
    latest_by_gap: dict[str, Job] = {}
    for job in jobs:
        gap_id = (job.payload or {}).get("gapSuggestionId")
        if gap_id and str(gap_id) not in latest_by_gap:
            latest_by_gap[str(gap_id)] = job

    outcomes: list[GapSearchOutcomeDTO] = []
    index = 0
    for suggestion in gap.suggestions:
        if suggestion.id not in selected:
            continue
        index += 1
        job = latest_by_gap.get(str(suggestion.id))
        if job is None:
            outcomes.append(
                GapSearchOutcomeDTO(
                    gap_suggestion_id=suggestion.id,
                    query_index=index,
                    outcome="PENDING",
                    result_count=0,
                    error_code=None,
                )
            )
            continue
        progress = job.progress or {}
        outcome = progress.get("outcome")
        if not outcome:
            if job.state in ACTIVE_JOB_STATES:
                outcome = "PENDING"
            elif job.state == JobState.FAILED.value:
                outcome = "FAILED"
            else:
                outcome = "PENDING"
        query_index = int((job.payload or {}).get("queryIndex") or index)
        result_count = int(progress.get("resultCount") or (job.payload or {}).get("resultCount") or 0)
        error_code = progress.get("errorCode") or job.last_error_code
        outcomes.append(
            GapSearchOutcomeDTO(
                gap_suggestion_id=suggestion.id,
                query_index=query_index,
                outcome=str(outcome),
                result_count=result_count,
                error_code=str(error_code) if error_code else None,
            )
        )
    return outcomes


def _digest_status(material: Material, digest: MaterialDigest | None) -> str:
    if digest is not None:
        return digest.status
    if material.status == MaterialStatus.FAILED.value:
        return "FAILED"
    return "PENDING"


async def current_digests(
    session: AsyncSession, materials: list[Material]
) -> dict[UUID, MaterialDigest]:
    if not materials:
        return {}
    ids = [m.id for m in materials]
    rows = list(
        (
            await session.scalars(
                select(MaterialDigest)
                .where(MaterialDigest.material_id.in_(ids), MaterialDigest.is_current.is_(True))
                .order_by(MaterialDigest.version)
            )
        ).all()
    )
    result: dict[UUID, MaterialDigest] = {}
    for row in rows:
        result[row.material_id] = row
    return result


def build_digest_items(
    materials: list[Material], digests: dict[UUID, MaterialDigest]
) -> list[MaterialDigestDTO]:
    return [
        MaterialDigestDTO(
            material_id=material.id,
            display_name=material.display_name,
            status=_digest_status(material, digests.get(material.id)),
            extracted_char_count=(digests.get(material.id).extracted_char_count if digests.get(material.id) else None),
            length_bucket=(digests.get(material.id).length_bucket if digests.get(material.id) else None),
            summary_preview=(digests.get(material.id).summary_preview if digests.get(material.id) else None),
        )
        for material in materials
    ]


def build_digest_state(
    materials: list[Material], digests: dict[UUID, MaterialDigest]
) -> DigestStateDTO:
    items = build_digest_items(materials, digests)
    if not materials:
        return DigestStateDTO(status="NONE", items=[])
    ready = sum(1 for item in items if item.status == "READY")
    if ready == len(items):
        status = "READY"
    elif ready > 0:
        status = "PARTIAL"
    else:
        status = "PENDING"
    return DigestStateDTO(status=status, items=items)


def source_item_dto(row: SourceItem) -> SourceItemDTO:
    return SourceItemDTO(
        id=row.id,
        origin=row.origin,
        source_type=row.source_type,
        title=row.title,
        summary=row.summary,
        domain=row.domain,
        rank=row.rank,
        material_id=row.material_id,
        gap_suggestion_id=row.gap_suggestion_id,
    )


async def active_search_job_exists(session: AsyncSession, project: Project) -> bool:
    value = await session.scalar(
        select(Job.id)
        .where(
            Job.project_id == project.id,
            Job.type == JobType.SEARCH.value,
            Job.state.in_(ACTIVE_JOB_STATES),
        )
        .limit(1)
    )
    return value is not None


async def build_source_panel(
    session: AsyncSession, project: Project, *, include_digest: bool = False
) -> SourcePanelDTO:
    settings = get_settings()
    materials = list(
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
    material_ids = {m.id for m in materials}
    provided_rows = list(
        (
            await session.scalars(
                select(SourceItem)
                .where(SourceItem.project_id == project.id, SourceItem.origin == "PROVIDED")
                .order_by(SourceItem.rank, SourceItem.created_at)
            )
        ).all()
    )
    provided = [row for row in provided_rows if row.material_id in material_ids]
    web_rows = list(
        (
            await session.scalars(
                select(SourceItem)
                .where(SourceItem.project_id == project.id, SourceItem.origin == "WEB")
                .order_by(SourceItem.rank, SourceItem.created_at)
            )
        ).all()
    )

    if not materials:
        materials_status = "empty"
    elif provided and all(m.status == MaterialStatus.DIGESTED.value for m in materials):
        materials_status = "ready"
    else:
        materials_status = "loading"

    web_status = "ready" if web_rows else ("loading" if await active_search_job_exists(session, project) else "empty")
    gap = await load_gap_context(session, project)

    digest_items = None
    if include_digest:
        digests = await current_digests(session, materials)
        digest_items = build_digest_items(materials, digests)

    return SourcePanelDTO(
        materials=SourceGroupDTO(
            count=len(provided),
            status=materials_status,
            items=[source_item_dto(row) for row in provided],
            digest=digest_items,
        ),
        web=WebSourceGroupDTO(
            count=len(web_rows),
            status=web_status,
            items=[source_item_dto(row) for row in web_rows],
            skipped=gap.web_skipped,
            cap=settings.search_cap_per_project,
        ),
    )


async def build_active_research_jobs(session: AsyncSession, project: Project) -> list[ActiveJobRef]:
    rows = list(
        (
            await session.scalars(
                select(Job)
                .where(
                    Job.project_id == project.id,
                    Job.state.in_(ACTIVE_JOB_STATES),
                    Job.type.in_(RESEARCH_JOB_TYPES),
                )
                .order_by(Job.created_at)
            )
        ).all()
    )
    refs: list[ActiveJobRef] = []
    for job in rows:
        page_id = None
        raw_page = (job.payload or {}).get("pageId")
        if raw_page:
            try:
                page_id = UUID(str(raw_page))
            except (TypeError, ValueError):
                page_id = None
        refs.append(ActiveJobRef(job_id=job.id, type=job.type, state=job.state, page_id=page_id))
    return refs


def _parse_uuid_list(raw: Any) -> list[UUID]:
    values: list[UUID] = []
    for item in raw or []:
        try:
            values.append(UUID(str(item)))
        except (TypeError, ValueError):
            continue
    return values


def profile_dto(profile: Any) -> ProfileDTO:
    materials_summary = profile.materials_summary or {}
    web_scope = profile.web_scope or {}
    return ProfileDTO(
        profile_version_id=profile.id,
        version=profile.version,
        audience=profile.audience,
        goal=profile.goal,
        style_mood=profile.style_mood,
        page_count=profile.page_count,
        materials_summary=MaterialsSummaryDTO(
            material_ids=_parse_uuid_list(
                materials_summary.get("materialIds", materials_summary.get("material_ids", []))
            ),
            material_count=int(
                materials_summary.get("materialCount", materials_summary.get("material_count", 0)) or 0
            ),
            strategy=str(materials_summary.get("strategy") or "web_only"),
        ),
        web_scope=WebScopeDTO(
            selected_gap_suggestion_ids=_parse_uuid_list(
                web_scope.get(
                    "selectedGapSuggestionIds",
                    web_scope.get("selected_gap_suggestion_ids", []),
                )
            ),
            web_skipped=bool(web_scope.get("webSkipped", web_scope.get("web_skipped", False))),
            source_count=int(web_scope.get("sourceCount", web_scope.get("source_count", 0)) or 0),
        ),
        content_strategy=profile.content_strategy,
        source_refs=_parse_uuid_list(profile.source_refs),
        created_at=profile.created_at,
    )


async def build_research_state(session: AsyncSession, project: Project) -> ResearchStateDTO:
    snapshot = await build_snapshot(session, project)
    research_stage = next((s for s in snapshot.stages if s.stage == "RESEARCH"), None)
    profile = await load_profile(session, project)
    dirty = await compute_profile_dirty(session, project, profile)
    questions = await load_questions(session, project)
    answers = await load_answers(session, project)
    materials = list(
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
    digests = await current_digests(session, materials)
    gap = await load_gap_context(session, project)
    sources = await build_source_panel(session, project, include_digest=True)

    return ResearchStateDTO(
        stage=project.stage,
        stage_status=research_stage.status if research_stage else "IN_PROGRESS",
        profile_dirty=dirty,
        questions=build_question_dtos(questions, answers),
        digest=build_digest_state(materials, digests),
        gaps=gap_state_dto(gap),
        gap_searches=await build_gap_searches(session, project, gap),
        sources=sources,
        profile=profile_dto(profile) if profile else None,
        counts=ResearchCountsDTO(
            questions_total=len(questions),
            questions_answered=len(answers),
            materials_selected=len(materials),
            selected_gaps=len(gap.selected_ids),
        ),
        active_jobs=await build_active_research_jobs(session, project),
    )


async def web_source_count(session: AsyncSession, project: Project) -> int:
    return int(
        await session.scalar(
            select(func.count())
            .select_from(SourceItem)
            .where(SourceItem.project_id == project.id, SourceItem.origin == "WEB")
        )
        or 0
    )


async def build_profile_inputs(session: AsyncSession, project: Project) -> ProfileInputs:
    questions = await load_questions(session, project)
    answers = await load_answers(session, project)
    materials = list(
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
    digests = await current_digests(session, materials)
    sources = list(
        (
            await session.scalars(
                select(SourceItem)
                .where(SourceItem.project_id == project.id)
                .order_by(SourceItem.created_at)
            )
        ).all()
    )
    gap = await load_gap_context(session, project)
    selected_gap_ids = await selected_gap_ids_all(session, project)
    web_skipped = gap.web_skipped

    answer_payload: dict[str, dict[str, str]] = {}
    for question in questions:
        answer = answers.get(question.question_key)
        if answer is None:
            continue
        answer_payload[question.question_key] = {
            "optionKey": answer.option_key,
            "label": option_label(question, answer.option_key),
        }

    fingerprint = profile_fingerprint(
        answers={key: value.option_key for key, value in answers.items()},
        material_ids=[str(m.id) for m in materials],
        gap_selected_ids=[str(gid) for gid in selected_gap_ids],
        web_skipped=web_skipped,
        source_ids=[str(s.id) for s in sources],
    )
    return ProfileInputs(
        questions=questions,
        answers=answers,
        answer_payload=answer_payload,
        materials=materials,
        digests=[
            {
                "materialId": str(m.id),
                "displayName": m.display_name,
                "summary": digests[m.id].summary_preview if m.id in digests else None,
            }
            for m in materials
            if m.id in digests and digests[m.id].status == "READY"
        ],
        sources=sources,
        gap=gap,
        selected_gap_ids=selected_gap_ids,
        web_skipped=web_skipped,
        fingerprint=fingerprint,
    )


def web_only_queries(topic: str) -> list[str]:
    clean = topic.strip().rstrip(".")
    return [
        f"{clean} overview and key facts",
        f"{clean} market and industry context",
        f"{clean} examples and case studies",
    ]


def gap_query(topic: str, label: str, reason: str) -> str:
    detail = " ".join((reason or "").split())
    return (f"{label} for {topic.strip()}. {detail[:160]}").strip()[:400]


# ---- Research gates, job planning, and content-free event payloads ---------


def assert_research_active(project: Project) -> None:
    if project.stage != Stage.RESEARCH.value:
        raise gate("error.gate.research_not_active")


def assert_research_started(project: Project) -> None:
    """Answer/profile edits remain possible after the outline exists [PRD FR-2.14]."""
    if project.stage == Stage.INTAKE.value:
        raise gate("error.gate.research_not_active")


async def all_materials_digested(session: AsyncSession, project: Project) -> bool:
    from app.services.materials import current_digest, list_active_materials

    materials = await list_active_materials(session, project)
    if not materials:
        return False
    for material in materials:
        digest = await current_digest(session, material.id)
        if digest is None or digest.status != "READY":
            return False
    return True


async def assert_digest_complete(session: AsyncSession, project: Project) -> None:
    from app.services.materials import list_active_materials

    materials = await list_active_materials(session, project)
    if not materials:
        return
    digests = await current_digests(session, materials)
    for material in materials:
        digest = digests.get(material.id)
        if digest is None or digest.status != "READY":
            raise gate("error.gate.digest_incomplete")


def char_count_bucket(count: int | None) -> str:
    if not count:
        return "none"
    if count < 2000:
        return "lt2k"
    if count < 10000:
        return "2k_10k"
    return "gte10k"


def clamp_page_count(value: Any) -> int:
    settings = get_settings()
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 10
    return max(6, min(number, min(16, settings.page_max_count)))


def source_added_payload(source: SourceItem) -> dict[str, Any]:
    """Content-free `sourceAdded` payload [API §6]."""
    payload: dict[str, Any] = {
        "sourceItemId": str(source.id),
        "origin": source.origin,
        "sourceType": source.source_type,
        "domain": source.domain,
        "rank": source.rank,
    }
    if source.material_id:
        payload["materialId"] = str(source.material_id)
    if source.gap_suggestion_id:
        payload["gapSuggestionId"] = str(source.gap_suggestion_id)
    return payload


def digest_ready_payload(
    material_id: UUID, *, length_bucket: str | None, extracted_char_count: int | None
) -> dict[str, Any]:
    return {
        "materialId": str(material_id),
        "status": "READY",
        "lengthBucket": length_bucket,
        "extractedCharBucket": char_count_bucket(extracted_char_count),
    }


def gateway_sources(sources: list[SourceItem]) -> list[dict[str, Any]]:
    """Model-bound source payload. Title/summary never enter events or logs."""
    return [
        {
            "sourceItemId": str(source.id),
            "origin": source.origin,
            "sourceType": source.source_type,
            "title": source.title,
            "summary": source.summary,
            "domain": source.domain,
        }
        for source in sources
    ]


def gap_answer_payload(answers: dict[str, InterviewAnswer]) -> dict[str, str]:
    return {key: answer.option_key for key, answer in answers.items()}


def materials_summary_payload(inputs: ProfileInputs) -> dict[str, Any]:
    return {
        "materialIds": [str(m.id) for m in inputs.materials],
        "materialCount": len(inputs.materials),
        "strategy": "material_first" if inputs.materials else "web_only",
    }


def web_scope_payload(inputs: ProfileInputs, source_count: int) -> dict[str, Any]:
    return {
        "selectedGapSuggestionIds": [str(gid) for gid in inputs.selected_gap_ids],
        "webSkipped": inputs.web_skipped,
        "sourceCount": source_count,
    }


async def next_profile_version(session: AsyncSession, project: Project) -> int:
    value = await session.scalar(
        select(func.max(RequirementsProfile.version)).where(RequirementsProfile.project_id == project.id)
    )
    return int(value or 0) + 1


async def digest_summaries(session: AsyncSession, project: Project) -> list[str]:
    from app.services.materials import list_active_materials

    materials = await list_active_materials(session, project)
    digests = await current_digests(session, materials)
    summaries: list[str] = []
    for material in materials:
        digest = digests.get(material.id)
        if digest is not None and digest.status == "READY" and digest.summary_preview:
            summaries.append(digest.summary_preview)
    return summaries


def web_search_operation_key(project_id: UUID, index: int) -> str:
    return f"search:{project_id}:web:{index}"


def gap_search_operation_key(project_id: UUID, gap_id: UUID) -> str:
    return f"search:{project_id}:gap:{gap_id}"


async def enqueue_web_only_searches(session: AsyncSession, project: Project) -> list[Job]:
    from app.services.jobs import enqueue_job

    jobs: list[Job] = []
    for index, query in enumerate(web_only_queries(project.topic), start=1):
        key = web_search_operation_key(project.id, index)
        jobs.append(
            await enqueue_job(
                session,
                project,
                JobType.SEARCH,
                operation_key=key,
                active_operation_key=key,
                payload={"query": query, "queryIndex": index},
            )
        )
    return jobs


async def enqueue_gap_search(
    session: AsyncSession, project: Project, suggestion: GapSuggestion, query_index: int
) -> Job:
    from app.services.jobs import enqueue_job

    operation_key = gap_search_operation_key(project.id, suggestion.id)
    return await enqueue_job(
        session,
        project,
        JobType.SEARCH,
        operation_key=operation_key,
        active_operation_key=operation_key,
        payload={
            "query": gap_query(project.topic, suggestion.label, suggestion.reason),
            "gapSuggestionId": str(suggestion.id),
            "queryIndex": query_index,
        },
    )


async def enqueue_gap_suggest(session: AsyncSession, project: Project) -> Job:
    from app.services.jobs import enqueue_job

    return await enqueue_job(
        session,
        project,
        JobType.GAP_SUGGEST,
        operation_key=f"gaps:{project.id}",
        active_operation_key=f"gaps:{project.id}",
        payload={},
    )


def gap_status_for(selected: bool) -> str:
    return GapStatus.SELECTED.value if selected else GapStatus.REJECTED.value


__all__ = [
    "QUESTION_CATALOG",
    "GapContext",
    "ProfileInputs",
    "active_search_job_exists",
    "all_materials_digested",
    "assert_digest_complete",
    "assert_research_active",
    "assert_research_started",
    "build_active_research_jobs",
    "build_digest_items",
    "build_digest_state",
    "build_gap_searches",
    "build_profile_inputs",
    "build_question_dtos",
    "build_research_state",
    "build_source_panel",
    "char_count_bucket",
    "clamp_page_count",
    "current_digests",
    "digest_ready_payload",
    "digest_summaries",
    "ensure_questions",
    "enqueue_gap_search",
    "enqueue_gap_suggest",
    "enqueue_web_only_searches",
    "gap_answer_payload",
    "gap_query",
    "gap_search_operation_key",
    "gap_state_dto",
    "gap_status_for",
    "gap_suggestion_dto",
    "gateway_sources",
    "latest_gap_batch",
    "load_answers",
    "load_gap_context",
    "load_questions",
    "materials_summary_payload",
    "next_profile_version",
    "option_keys",
    "option_label",
    "profile_dto",
    "selected_gap_ids_all",
    "source_added_payload",
    "source_item_dto",
    "web_only_queries",
    "web_scope_payload",
    "web_search_operation_key",
    "web_source_count",
]
