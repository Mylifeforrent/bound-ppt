from __future__ import annotations

import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

# Environment MUST be set before any app module is imported: app.core.db creates
# the engine at import time from the cached Settings object.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="bound-ppt-research-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_ROOT / 'test.db'}"
os.environ["STORAGE_LOCAL_ROOT"] = str(_TEST_ROOT / "storage")
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["MODEL_PROVIDER"] = "stub"
os.environ["SEARCH_PROVIDER"] = "stub"

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionFactory, init_db  # noqa: E402
from app.core.ids import new_id, utcnow  # noqa: E402
from app.core.security import create_session, seed_pilot_user  # noqa: E402
from app.ingest.search import search  # noqa: E402
from app.llm.gateway import gateway  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    DomainEvent,
    GapSuggestion,
    Job,
    Material,
    MaterialDigest,
    OutlinePageVersion,
    OutlineVersion,
    Page,
    Project,
    RequirementsProfile,
    SourceItem,
)
from app.storage import storage  # noqa: E402
from app.worker import handlers as _worker_handlers  # noqa: E402,F401  (registers handlers)
from app.worker.runner import HANDLERS, JobContext  # noqa: E402

NOTICE_VERSION = "2026-11-01"


@pytest.fixture
async def client():
    await init_db()
    async with SessionFactory() as session:
        user = await seed_pilot_user(session)
        token, _ = await create_session(session, user.id)
        await session.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        http.cookies.set("bound_session", token)
        yield http


async def _accept_consent(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/policy/consent",
        json={"noticeType": "DATA_NOTICE", "version": NOTICE_VERSION},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 200, response.text


async def _create_project(client: httpx.AsyncClient, *, topic: str = "Market entry plan") -> dict:
    response = await client.post(
        "/api/projects",
        json={"topic": topic},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["project"]


async def _version(client: httpx.AsyncClient, project_id: str) -> int:
    response = await client.get(f"/api/projects/{project_id}/snapshot")
    assert response.status_code == 200, response.text
    return int(response.json()["meta"]["projectVersion"])


async def _paste(client: httpx.AsyncClient, project_id: str, text: str) -> httpx.Response:
    version = await _version(client, project_id)
    return await client.post(
        f"/api/projects/{project_id}/materials/paste",
        json={"text": text, "displayName": "Pasted brief"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(version)},
    )


async def _run_job(job_id: UUID) -> str:
    async with SessionFactory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.state = "RUNNING"
        job.attempt_count += 1
        job.fencing_token += 1
        job.lease_owner = "test-worker"
        job.lease_expires_at = utcnow()
        await session.flush()
        ctx = JobContext(
            session=session,
            job=job,
            attempt_id=new_id(),
            fencing_token=job.fencing_token,
            settings=get_settings(),
            gateway=gateway,
            search=search,
            storage=storage,
            worker_id="test-worker",
        )
        await HANDLERS[job.type](ctx)
        if job.state == "RUNNING":
            job.state = "SUCCEEDED"
            job.active_operation_key = None
            job.completed_at = utcnow()
        await session.commit()
        return job.type


async def _job_for(project_id: UUID, job_type: str, *, material_id: UUID | None = None) -> Job | None:
    async with SessionFactory() as session:
        rows = list(
            (
                await session.scalars(
                    select(Job)
                    .where(Job.project_id == project_id, Job.type == job_type)
                    .order_by(Job.created_at.desc())
                )
            ).all()
        )
    for job in rows:
        if material_id is None:
            return job
        if str((job.payload or {}).get("materialId")) == str(material_id):
            return job
    return None


async def _events(project_id: UUID) -> list[str]:
    async with SessionFactory() as session:
        rows = (
            await session.scalars(
                select(DomainEvent)
                .where(DomainEvent.project_id == project_id)
                .order_by(DomainEvent.sequence)
            )
        ).all()
    return [row.type for row in rows]


async def _answer(client: httpx.AsyncClient, project_id: str, key: str, option: str) -> dict:
    version = await _version(client, project_id)
    response = await client.put(
        f"/api/projects/{project_id}/research/answers/{key}",
        json={"optionKey": option},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(version)},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_consent_paste_ingest_digest_gaps_search_profile(client: httpx.AsyncClient):
    project = await _create_project(client)
    project_id = project["id"]

    blocked = await _paste(client, project_id, "First-party facts about the market.")
    assert blocked.status_code == 409, blocked.text
    assert blocked.json()["error"]["messageKey"] == "error.gate.consent_required"
    assert blocked.json()["error"]["details"]["noticeType"] == "DATA_NOTICE"

    await _accept_consent(client)
    pasted = await _paste(client, project_id, "First-party facts about the market. Retention is rising.")
    assert pasted.status_code == 202, pasted.text
    paste_data = pasted.json()["data"]
    material_id = UUID(paste_data["material"]["id"])
    ingest_job_id = UUID(paste_data["jobId"])
    assert paste_data["material"]["kind"] == "PASTE"
    assert paste_data["material"]["status"] == "PENDING"
    assert pasted.json()["meta"]["projectVersion"] == 2

    listed = await client.get(f"/api/projects/{project_id}/materials")
    assert listed.status_code == 200, listed.text
    list_data = listed.json()["data"]
    assert list_data["limit"] == get_settings().material_max_count
    assert list_data["remaining"] == list_data["limit"] - 1
    assert list_data["materials"][0]["activeJob"]["jobId"] == str(ingest_job_id)

    assert await _run_job(ingest_job_id) == "INGEST"
    async with SessionFactory() as session:
        material = await session.get(Material, material_id)
        assert material is not None
        assert material.status == "DIGESTED"
        assert material.content_ref
        provided = list(
            (
                await session.scalars(
                    select(SourceItem).where(
                        SourceItem.project_id == UUID(project_id),
                        SourceItem.origin == "PROVIDED",
                    )
                )
            ).all()
        )
        assert len(provided) == 1
        assert provided[0].material_id == material_id
        assert provided[0].source_type == "PASTE"
    material_events = await _events(UUID(project_id))
    assert "materialStatusChanged" in material_events
    assert "sourceAdded" in material_events

    digest_job = await _job_for(UUID(project_id), "DIGEST", material_id=material_id)
    assert digest_job is not None
    assert digest_job.state == "QUEUED"
    assert await _run_job(digest_job.id) == "DIGEST"
    async with SessionFactory() as session:
        digest = await session.scalar(
            select(MaterialDigest).where(
                MaterialDigest.material_id == material_id, MaterialDigest.is_current.is_(True)
            )
        )
        assert digest is not None
        assert digest.status == "READY"
        assert digest.summary_preview
        assert digest.extracted_char_count and digest.extracted_char_count > 0
        assert digest.length_bucket in {"short", "medium", "long"}
    assert "digestReady" in await _events(UUID(project_id))

    gap_job = await _job_for(UUID(project_id), "GAP_SUGGEST")
    assert gap_job is not None
    assert gap_job.state == "QUEUED"
    assert await _run_job(gap_job.id) == "GAP_SUGGEST"
    async with SessionFactory() as session:
        suggestions = list(
            (
                await session.scalars(
                    select(GapSuggestion)
                    .where(GapSuggestion.project_id == UUID(project_id))
                    .order_by(GapSuggestion.position)
                )
            ).all()
        )
        assert len(suggestions) == 3
        assert {row.batch for row in suggestions} == {1}
        assert {row.status for row in suggestions} == {"SUGGESTED"}
        suggestion_ids = [str(row.id) for row in suggestions]
    assert "gapSuggested" in await _events(UUID(project_id))

    start_version = await _version(client, project_id)
    started = await client.post(
        f"/api/projects/{project_id}/research/start",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(start_version)},
    )
    assert started.status_code == 202, started.text
    start_data = started.json()["data"]
    assert start_data["stage"] == "RESEARCH"
    assert start_data["stageStatus"] == "IN_PROGRESS"
    assert started.json()["meta"]["projectVersion"] == start_version + 1

    research = await client.get(f"/api/projects/{project_id}/research")
    assert research.status_code == 200, research.text
    research_data = research.json()["data"]
    assert [q["key"] for q in research_data["questions"]] == ["audience", "goal", "style", "length"]
    assert all(q["answer"] is None for q in research_data["questions"])
    assert research_data["digest"]["status"] == "READY"
    assert research_data["gaps"]["batch"] == 1
    assert len(research_data["gaps"]["suggestions"]) == 3
    assert research_data["profile"] is None
    project_events = await _events(UUID(project_id))
    assert project_events.count("questionAsked") == 4
    assert "stageStateChanged" in project_events

    decision_version = await _version(client, project_id)
    decided = await client.post(
        f"/api/projects/{project_id}/research/gaps/decisions",
        json={"selectedSuggestionIds": [suggestion_ids[0], suggestion_ids[2]], "webSkipped": False},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(decision_version)},
    )
    assert decided.status_code == 202, decided.text
    decision_data = decided.json()["data"]
    assert len(decision_data["searchJobIds"]) == 2
    assert [row["outcome"] for row in decision_data["gapSearches"]] == ["PENDING", "PENDING"]
    assert decision_data["gaps"]["decision"]["selectedSuggestionIds"] == [
        suggestion_ids[0],
        suggestion_ids[2],
    ]
    assert "gapDecided" in await _events(UUID(project_id))

    search_ids = [UUID(raw) for raw in decision_data["searchJobIds"]]
    for search_id in search_ids:
        assert await _run_job(search_id) == "SEARCH"
    async with SessionFactory() as session:
        web_sources = list(
            (
                await session.scalars(
                    select(SourceItem).where(
                        SourceItem.project_id == UUID(project_id), SourceItem.origin == "WEB"
                    )
                )
            ).all()
        )
        assert len(web_sources) == 6
        assert all(row.source_type == "WEB_RESULT" for row in web_sources)
        assert all(row.url_hash for row in web_sources)
        for search_id in search_ids:
            job = await session.get(Job, search_id)
            assert job is not None
            assert job.progress["outcome"] == "RESULTS"
            assert job.progress["resultCount"] == 3
            assert job.payload["resultCount"] == 3
    workspace_events = await _events(UUID(project_id))
    assert workspace_events.count("gapSearchCompleted") == 2
    assert workspace_events.count("sourceAdded") == 7  # 1 provided + 6 web

    research_after_search = await client.get(f"/api/projects/{project_id}/research")
    outcomes = research_after_search.json()["data"]["gapSearches"]
    assert [row["outcome"] for row in outcomes] == ["RESULTS", "RESULTS"]
    assert all(row["resultCount"] == 3 for row in outcomes)

    first = await _answer(client, project_id, "audience", "investors")
    assert first["question"]["revision"] == 1
    assert first["profileDirty"] is False
    second = await _answer(client, project_id, "audience", "prospects")
    assert second["question"]["revision"] == 2
    assert second["profileDirty"] is False
    await _answer(client, project_id, "goal", "fundraise")
    await _answer(client, project_id, "style", "tech")
    await _answer(client, project_id, "length", "medium")
    assert "answerRecorded" in await _events(UUID(project_id))

    profile_version = await _version(client, project_id)
    profile_response = await client.post(
        f"/api/projects/{project_id}/research/profile",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(profile_version)},
    )
    assert profile_response.status_code == 200, profile_response.text
    profile_data = profile_response.json()["data"]
    profile = profile_data["profile"]
    assert profile["version"] == 1
    assert profile["audience"] == "Prospects and partners"
    assert profile["goal"] == "Fundraising roadshow"
    assert profile["styleMood"] == "Techy · dark and bold"
    assert profile["pageCount"] == 10
    assert profile["materialsSummary"]["strategy"] == "material_first"
    assert profile["materialsSummary"]["materialIds"] == [str(material_id)]
    assert set(profile["webScope"]["selectedGapSuggestionIds"]) == {
        suggestion_ids[0],
        suggestion_ids[2],
    }
    assert profile["webScope"]["sourceCount"] == 6
    assert profile["sourceRefs"]
    assert profile_data["profileDirty"] is False
    assert profile_data["outlineUnconfirmed"] is False
    assert profile_data["stale"] is None
    assert profile_response.json()["meta"]["projectVersion"] == profile_version + 1
    assert "profileReady" in await _events(UUID(project_id))
    async with SessionFactory() as session:
        row = await session.get(RequirementsProfile, UUID(profile["profileVersionId"]))
        assert row is not None
        assert row.input_fingerprint
        assert row.web_skipped is False
        assert row.materials_summary["materialCount"] == 1

    clean_version = await _version(client, project_id)
    replayed = await client.post(
        f"/api/projects/{project_id}/research/profile",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(clean_version)},
    )
    assert replayed.status_code == 200, replayed.text
    assert replayed.json()["data"]["profile"]["profileVersionId"] == profile["profileVersionId"]
    assert replayed.json()["meta"]["projectVersion"] == clean_version
    async with SessionFactory() as session:
        rows = list(
            (
                await session.scalars(
                    select(RequirementsProfile).where(
                        RequirementsProfile.project_id == UUID(project_id)
                    )
                )
            ).all()
        )
        assert len(rows) == 1

    sources = await client.get(f"/api/projects/{project_id}/sources")
    assert sources.status_code == 200, sources.text
    panel = sources.json()["data"]
    assert panel["materials"]["count"] == 1
    assert panel["materials"]["status"] == "ready"
    assert panel["web"]["count"] == 6
    assert panel["web"]["status"] == "ready"


async def test_material_limit_gate(client: httpx.AsyncClient):
    project = await _create_project(client, topic="Limit test")
    project_id = project["id"]
    await _accept_consent(client)
    limit = get_settings().material_max_count

    for index in range(limit):
        response = await _paste(client, project_id, f"Material body {index} with enough text to digest.")
        assert response.status_code == 202, response.text

    over = await _paste(client, project_id, "One material too many.")
    assert over.status_code == 409, over.text
    error = over.json()["error"]
    assert error["messageKey"] == "error.gate.material_limit"
    assert error["details"]["limit"] == limit
    assert error["details"]["currentCount"] == limit

    listed = await client.get(f"/api/projects/{project_id}/materials")
    assert listed.status_code == 200
    assert len(listed.json()["data"]["materials"]) == limit
    assert listed.json()["data"]["remaining"] == 0


async def test_invalid_url_and_unknown_answer(client: httpx.AsyncClient):
    project = await _create_project(client, topic="Validation test")
    project_id = project["id"]
    await _accept_consent(client)

    version = await _version(client, project_id)
    bad_url = await client.post(
        f"/api/projects/{project_id}/materials/url",
        json={"url": "ftp://example.com/file"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(version)},
    )
    assert bad_url.status_code == 422, bad_url.text
    assert bad_url.json()["error"]["messageKey"] == "error.validation.invalid_url"

    start_version = await _version(client, project_id)
    started = await client.post(
        f"/api/projects/{project_id}/research/start",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(start_version)},
    )
    assert started.status_code == 202, started.text
    search_job_ids = [UUID(raw) for raw in started.json()["data"]["jobIds"]]
    assert len(search_job_ids) == 3  # web-only plan enqueues three SEARCH jobs
    for search_id in search_job_ids:
        assert await _run_job(search_id) == "SEARCH"

    answer_version = await _version(client, project_id)
    unknown = await client.put(
        f"/api/projects/{project_id}/research/answers/unknown",
        json={"optionKey": "anything"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(answer_version)},
    )
    assert unknown.status_code == 422, unknown.text
    assert unknown.json()["error"]["messageKey"] == "error.validation.unknown_question"

    answer_version = await _version(client, project_id)
    bad_option = await client.put(
        f"/api/projects/{project_id}/research/answers/audience",
        json={"optionKey": "not-an-option"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(answer_version)},
    )
    assert bad_option.status_code == 422, bad_option.text
    assert bad_option.json()["error"]["messageKey"] == "error.validation.unknown_option"

    for key, option in (
        ("audience", "public"),
        ("goal", "brand"),
        ("style", "minimal"),
        ("length", "short"),
    ):
        await _answer(client, project_id, key, option)

    profile_version = await _version(client, project_id)
    profile_response = await client.post(
        f"/api/projects/{project_id}/research/profile",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(profile_version)},
    )
    assert profile_response.status_code == 200, profile_response.text
    profile = profile_response.json()["data"]["profile"]
    assert profile["materialsSummary"] == {
        "materialIds": [],
        "materialCount": 0,
        "strategy": "web_only",
    }
    assert profile["webScope"]["webSkipped"] is False
    assert profile["webScope"]["sourceCount"] == 9
    assert profile["pageCount"] == 7


async def test_upload_url_finalize_and_delete(client: httpx.AsyncClient):
    project = await _create_project(client, topic="Upload flow")
    project_id = project["id"]
    await _accept_consent(client)
    body = b"Uploaded text file content with enough words to be digestible."

    version = await _version(client, project_id)
    presigned = await client.post(
        f"/api/projects/{project_id}/materials/upload-url",
        json={"fileName": "brief.txt", "mimeType": "text/plain", "sizeBytes": len(body)},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(version)},
    )
    assert presigned.status_code == 200, presigned.text
    instruction = presigned.json()["data"]
    material_id = instruction["materialId"]
    assert instruction["upload"]["method"] == "PUT"
    assert instruction["upload"]["url"].startswith("/api/uploads/")

    uploaded = await client.put(
        instruction["upload"]["url"], content=body, headers={"Content-Type": "text/plain"}
    )
    assert uploaded.status_code == 200, uploaded.text

    finalize_version = await _version(client, project_id)
    finalized = await client.post(
        f"/api/projects/{project_id}/materials/{material_id}/finalize",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(finalize_version)},
    )
    assert finalized.status_code == 202, finalized.text
    finalize_data = finalized.json()["data"]
    assert finalize_data["material"]["status"] == "PENDING"
    assert finalize_data["material"]["mimeType"] == "text/plain"
    assert finalize_data["material"]["sizeBytes"] == len(body)
    assert await _run_job(UUID(finalize_data["jobId"])) == "INGEST"

    async with SessionFactory() as session:
        material = await session.get(Material, UUID(material_id))
        assert material is not None
        assert material.status == "DIGESTED"
        assert material.content_ref
        assert material.raw_ref
        assert material.page_count is None

    delete_version = await _version(client, project_id)
    removed = await client.delete(
        f"/api/projects/{project_id}/materials/{material_id}",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(delete_version)},
    )
    assert removed.status_code == 200, removed.text
    removed_data = removed.json()["data"]
    assert removed_data["materialId"] == material_id
    assert removed_data["removed"] is True
    assert removed_data["stale"] is None

    listed = await client.get(f"/api/projects/{project_id}/materials")
    assert listed.status_code == 200
    assert listed.json()["data"]["materials"] == []
    assert listed.json()["data"]["remaining"] == get_settings().material_max_count


async def test_profile_update_unconfirms_outline_and_marks_stale(client: httpx.AsyncClient):
    project = await _create_project(client, topic="Outline refresh")
    project_id = project["id"]
    await _accept_consent(client)

    start_version = await _version(client, project_id)
    started = await client.post(
        f"/api/projects/{project_id}/research/start",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(start_version)},
    )
    assert started.status_code == 202, started.text
    for raw in started.json()["data"]["jobIds"]:
        await _run_job(UUID(raw))
    for key, option in (
        ("audience", "investors"),
        ("goal", "promote"),
        ("style", "business"),
        ("length", "long"),
    ):
        await _answer(client, project_id, key, option)

    profile_version = await _version(client, project_id)
    first = await client.post(
        f"/api/projects/{project_id}/research/profile",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(profile_version)},
    )
    assert first.status_code == 200, first.text
    assert first.json()["data"]["profile"]["version"] == 1

    # Simulate a generated+confirmed outline (the outline module owns this normally).
    async with SessionFactory() as session:
        page = Page(id=new_id(), project_id=UUID(project_id), page_type="BODY")
        session.add(page)
        await session.flush()
        outline = OutlineVersion(
            id=new_id(),
            project_id=UUID(project_id),
            version=1,
            confirmed_at=utcnow(),
            confirmed_by_user_id=None,
            input_fingerprint="outline-fingerprint",
            schema_version=1,
        )
        session.add(outline)
        await session.flush()
        session.add(
            OutlinePageVersion(
                id=new_id(),
                outline_version_id=outline.id,
                page_id=page.id,
                position=1,
                section_key="context",
                title="Context page",
                page_type="BODY",
                key_points=["Point"],
            )
        )
        row = await session.get(Project, UUID(project_id))
        assert row is not None
        row.current_outline_version_id = outline.id
        row.stage = "OUTLINE"
        await session.commit()
        page_id = str(page.id)
        outline_id = outline.id

    changed = await _answer(client, project_id, "audience", "public")
    assert changed["question"]["revision"] == 2
    assert changed["profileDirty"] is True
    assert changed["stale"] is None

    update_version = await _version(client, project_id)
    updated = await client.post(
        f"/api/projects/{project_id}/research/profile",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": str(update_version)},
    )
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["profile"]["version"] == 2
    assert data["profileDirty"] is False
    assert data["outlineUnconfirmed"] is True
    assert data["stale"]["changed"] is True
    assert data["stale"]["cause"] == "PROFILE_UPDATE"
    assert data["stale"]["affected"]["plan"] == [page_id]
    assert data["stale"]["affected"]["design"] == [page_id]
    assert data["stale"]["rerun"] == {"plan": 1, "design": 1}
    assert updated.json()["meta"]["projectVersion"] == update_version + 1

    async with SessionFactory() as session:
        outline_row = await session.get(OutlineVersion, outline_id)
        assert outline_row is not None
        assert outline_row.confirmed_at is None
        project_row = await session.get(Project, UUID(project_id))
        assert project_row is not None
        assert project_row.current_profile_version_id == UUID(data["profile"]["profileVersionId"])
    events_list = await _events(UUID(project_id))
    assert events_list.count("profileReady") == 1
    assert events_list.count("profileUpdated") == 1
    assert "staleChanged" in events_list
