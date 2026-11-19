from __future__ import annotations

import os
import tempfile
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

# Environment MUST be set before importing app modules (engine built at import).
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="bound-ppt-gen-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_ROOT / 'test.db'}"
os.environ["STORAGE_LOCAL_ROOT"] = str(_TEST_ROOT / "storage")
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["MODEL_PROVIDER"] = "stub"
os.environ["SEARCH_PROVIDER"] = "stub"

import httpx  # noqa: E402
import pytest  # noqa: E402
from pptx import Presentation  # noqa: E402
from sqlalchemy import select  # noqa: E402

import app.worker.handlers as worker_handlers  # noqa: E402,F401  (registers handlers)
from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionFactory, init_db  # noqa: E402
from app.core.ids import new_id, utcnow  # noqa: E402
from app.core.security import create_session, seed_pilot_user  # noqa: E402
from app.domain.fingerprints import profile_fingerprint  # noqa: E402
from app.ingest.search import search  # noqa: E402
from app.llm.gateway import gateway  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    DomainEvent,
    ExportArtifact,
    Job,
    Project,
    RequirementsProfile,
)
from app.services.events import bus  # noqa: E402
from app.storage import storage  # noqa: E402
from app.worker.runner import HANDLERS, JobContext  # noqa: E402


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


def _headers(version: int, key: str | None = None) -> dict[str, str]:
    return {"Idempotency-Key": key or str(uuid4()), "X-Expected-Version": str(version)}


async def _create_project(client: httpx.AsyncClient, topic: str = "Quarterly review") -> str:
    response = await client.post(
        "/api/projects", json={"topic": topic}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["project"]["id"]


async def _snapshot(client: httpx.AsyncClient, project_id: str) -> dict:
    response = await client.get(f"/api/projects/{project_id}/snapshot")
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _version(client: httpx.AsyncClient, project_id: str) -> int:
    return int((await _snapshot(client, project_id))["project"]["version"])


async def _seed_profile(project_id: UUID, page_count: int = 7) -> None:
    fingerprint = profile_fingerprint(
        answers={},
        material_ids=[],
        gap_selected_ids=[],
        web_skipped=True,
        source_ids=[],
    )
    async with SessionFactory() as session:
        project = await session.get(Project, project_id)
        profile = RequirementsProfile(
            id=new_id(),
            project_id=project_id,
            version=1,
            audience="Executive committee",
            goal="Approve the plan",
            style_mood="Confident and editorial",
            page_count=page_count,
            materials_summary={},
            web_scope={},
            web_skipped=True,
            content_strategy="Material-first",
            source_refs=[],
            input_fingerprint=fingerprint,
        )
        session.add(profile)
        await session.flush()
        project.current_profile_version_id = profile.id
        await session.commit()


async def _run_job(job_id: UUID) -> None:
    async with SessionFactory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        job.state = "RUNNING"
        job.attempt_count = (job.attempt_count or 0) + 1
        job.fencing_token = (job.fencing_token or 0) + 1
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
            job.completed_at = utcnow()
            job.active_operation_key = None
            job.lease_owner = None
            job.lease_expires_at = None
        await session.commit()


async def _run_jobs(job_ids: list[str]) -> None:
    for job_id in job_ids:
        await _run_job(UUID(job_id))


async def _pages(client: httpx.AsyncClient, project_id: str) -> dict:
    response = await client.get(f"/api/projects/{project_id}/pages")
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def _page_status(client: httpx.AsyncClient, project_id: str, page_id: str) -> dict:
    data = await _pages(client, project_id)
    return next(page for page in data["pages"] if page["pageId"] == page_id)


async def _export_bytes(export_id: UUID) -> bytes:
    async with SessionFactory() as session:
        artifact = await session.scalar(
            select(ExportArtifact).where(ExportArtifact.export_job_id == export_id)
        )
        assert artifact is not None
        assert artifact.byte_size > 0
        return storage.get_bytes(artifact.object_key)


async def _generate_outline(client: httpx.AsyncClient, project_id: str) -> str:
    version = await _version(client, project_id)
    response = await client.post(
        f"/api/projects/{project_id}/outline/generate", headers=_headers(version)
    )
    assert response.status_code == 202, response.text
    data = response.json()["data"]
    assert data["outlineVersionId"] is None
    return data["jobId"]


async def _confirm_outline(client: httpx.AsyncClient, project_id: str) -> dict:
    version = await _version(client, project_id)
    response = await client.post(
        f"/api/projects/{project_id}/outline/confirm", headers=_headers(version)
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_outline_plan_design_undo_export(client: httpx.AsyncClient):
    project_id = await _create_project(client)
    await _seed_profile(UUID(project_id), page_count=7)

    # ---- Styles catalog (lazy seed) -------------------------------------
    styles = await client.get("/api/styles")
    assert styles.status_code == 200, styles.text
    catalog = styles.json()["data"]["styles"]
    assert {style["styleKey"] for style in catalog} == {
        "editorial-indigo",
        "fresh-teal",
        "mono-graphite",
        "warm-amber",
    }
    one = await client.get("/api/styles/editorial-indigo?version=1")
    assert one.status_code == 200, one.text

    # ---- Outline generation (job + ephemeral deltas) --------------------
    outline_job_id = await _generate_outline(client, project_id)
    queue = bus.subscribe(UUID(project_id))
    try:
        await _run_job(UUID(outline_job_id))
        frames = []
        while not queue.empty():
            frames.append(queue.get_nowait())
    finally:
        bus.unsubscribe(UUID(project_id), queue)
    deltas = [
        frame["payload"]
        for frame in frames
        if frame.get("_frame") == "ephemeral" and frame["payload"].get("type") == "outlineDelta"
    ]
    assert deltas, frames
    assert [delta["chunkIndex"] for delta in deltas] == list(range(1, len(deltas) + 1))
    assert all(delta["jobId"] == outline_job_id for delta in deltas)

    response = await client.get(f"/api/projects/{project_id}/outline")
    assert response.status_code == 200, response.text
    outline = response.json()["data"]
    assert outline["confirmed"] is False
    assert outline["counts"]["pages"] == 7
    assert outline["counts"]["sections"] == 4
    assert outline["counts"]["bodyPages"] == 4
    assert outline["counts"]["agreedPageCount"] == 7
    assert outline["counts"]["deviation"] == 0
    assert outline["counts"]["deviationWarning"] is False
    page_types = [page["pageType"] for page in outline["pages"]]
    assert page_types == ["COVER", "TOC", "BODY", "BODY", "BODY", "BODY", "END"]
    assert outline["pages"][0]["deletable"] is False
    body_page_id = next(page["pageId"] for page in outline["pages"] if page["pageType"] == "BODY")

    # ---- Confirm outline -------------------------------------------------
    confirmed = await _confirm_outline(client, project_id)
    assert confirmed["outline"]["confirmed"] is True
    assert confirmed["stage"]["stage"] == "OUTLINE"
    assert confirmed["snapshot"]["pointers"]["outlineVersionId"] == outline["outlineVersionId"]

    # ---- Plan fan-out ----------------------------------------------------
    version = await _version(client, project_id)
    plan_generate = await client.post(
        f"/api/projects/{project_id}/plan/generate", headers=_headers(version)
    )
    assert plan_generate.status_code == 202, plan_generate.text
    plan_payload = plan_generate.json()["data"]
    assert plan_payload["counts"] == {"required": 7, "scheduled": 7, "reused": 0}
    assert plan_payload["skippedPageIds"] == []
    await _run_jobs([job["jobId"] for job in plan_payload["jobs"]])

    pages = await _pages(client, project_id)
    assert pages["counts"]["planDone"] == 7
    assert all(page["plan"]["status"] == "DONE" for page in pages["pages"])
    async with SessionFactory() as session:
        done_events = list(
            await session.scalars(
                select(DomainEvent.type).where(
                    DomainEvent.project_id == UUID(project_id),
                    DomainEvent.type == "pageJobDone",
                )
            )
        )
    assert len(done_events) == 7

    artifact = await client.get(
        f"/api/projects/{project_id}/pages/{body_page_id}/artifacts/plan"
    )
    assert artifact.status_code == 200, artifact.text
    assert artifact.headers["etag"].strip('"') == artifact.json()["data"]["contentDigest"]
    plan_body = artifact.json()["data"]["body"]
    assert plan_body["layoutId"] in {"single", "two_col", "three_col", "hero", "async", "mix"}
    assert len(plan_body["blocks"]) >= 1
    assert artifact.json()["data"]["chrome"]["pageNumber"] == 3
    history = await client.get(
        f"/api/projects/{project_id}/pages/{body_page_id}/history?kind=plan"
    )
    assert history.status_code == 200
    assert history.json()["data"]["depth"] == 0

    # ---- Style selection and confirmation -------------------------------
    version = await _version(client, project_id)
    selected = await client.put(
        f"/api/projects/{project_id}/style",
        json={"styleKey": "editorial-indigo", "styleVersion": 1, "rememberPreference": True},
        headers=_headers(version),
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["data"]["styleSelection"]["confirmed"] is False
    version = await _version(client, project_id)
    style_confirm = await client.post(
        f"/api/projects/{project_id}/style/confirm", headers=_headers(version)
    )
    assert style_confirm.status_code == 200, style_confirm.text
    assert style_confirm.json()["data"]["styleSelection"]["confirmed"] is True
    assert style_confirm.json()["data"]["stage"]["stage"] == "STYLE"

    # ---- Design fan-out --------------------------------------------------
    version = await _version(client, project_id)
    design_generate = await client.post(
        f"/api/projects/{project_id}/design/generate", headers=_headers(version)
    )
    assert design_generate.status_code == 202, design_generate.text
    design_payload = design_generate.json()["data"]
    assert len(design_payload["jobs"]) == 7
    await _run_jobs([job["jobId"] for job in design_payload["jobs"]])
    pages = await _pages(client, project_id)
    assert pages["counts"]["designDone"] == 7
    async with SessionFactory() as session:
        design_events = list(
            await session.scalars(
                select(DomainEvent.payload).where(
                    DomainEvent.project_id == UUID(project_id),
                    DomainEvent.type == "pageJobDone",
                )
            )
        )
    assert sum(1 for payload in design_events if payload.get("kind") == "DESIGN") == 7
    design_artifact = await client.get(
        f"/api/projects/{project_id}/pages/{body_page_id}/artifacts/design"
    )
    assert design_artifact.status_code == 200
    assert design_artifact.json()["data"]["body"]["style"]["styleKey"] == "editorial-indigo"

    # ---- Plan tweak -> design stale -> design tweak -> plan undo ---------
    version = await _version(client, project_id)
    tweak = await client.post(
        f"/api/projects/{project_id}/pages/{body_page_id}/plan/tweak",
        json={"instruction": "Tighten the headline"},
        headers=_headers(version),
    )
    assert tweak.status_code == 202, tweak.text
    async with SessionFactory() as session:
        job = await session.get(Job, UUID(tweak.json()["data"]["jobId"]))
        assert job.instruction_ref is not None
        assert "Tighten" not in str(job.payload)
    await _run_job(UUID(tweak.json()["data"]["jobId"]))
    tweaked_page = await _page_status(client, project_id, body_page_id)
    assert tweaked_page["plan"]["version"] == 2
    assert tweaked_page["design"]["status"] == "STALE"

    version = await _version(client, project_id)
    design_tweak = await client.post(
        f"/api/projects/{project_id}/pages/{body_page_id}/design/tweak",
        json={"instruction": "Use the accent color"},
        headers=_headers(version),
    )
    assert design_tweak.status_code == 202, design_tweak.text
    await _run_job(UUID(design_tweak.json()["data"]["jobId"]))
    rebuilt = await _page_status(client, project_id, body_page_id)
    assert rebuilt["design"]["status"] == "DONE"
    assert rebuilt["design"]["version"] == 2

    version = await _version(client, project_id)
    undo = await client.post(
        f"/api/projects/{project_id}/pages/{body_page_id}/undo",
        json={"kind": "plan"},
        headers=_headers(version),
    )
    assert undo.status_code == 200, undo.text
    undo_data = undo.json()["data"]
    assert undo_data["artifact"]["version"] == 1
    assert undo_data["history"]["depth"] == 0
    assert body_page_id in [str(pid) for pid in undo_data["stale"]["affected"]["design"]]
    after_undo = await _page_status(client, project_id, body_page_id)
    assert after_undo["design"]["status"] == "STALE"

    # ---- Reuse: restore the design that matches plan v1 with zero jobs ---
    version = await _version(client, project_id)
    reuse = await client.post(
        f"/api/projects/{project_id}/design/generate", headers=_headers(version)
    )
    assert reuse.status_code == 202, reuse.text
    reuse_payload = reuse.json()["data"]
    assert reuse_payload["jobs"] == []
    assert body_page_id in reuse_payload["skippedPageIds"]
    assert reuse_payload["counts"]["reused"] == 7
    pages = await _pages(client, project_id)
    assert pages["counts"]["designDone"] == 7

    # ---- Export PPTX / HTML / PDF ---------------------------------------
    version = await _version(client, project_id)
    create = await client.post(
        f"/api/projects/{project_id}/exports", json={"format": "PPTX"}, headers=_headers(version)
    )
    assert create.status_code == 202, create.text
    export_data = create.json()["data"]["export"]
    assert export_data["state"] == "QUEUED"
    assert export_data["deckSnapshot"] == {
        "pageCount": 7,
        "styleKey": "editorial-indigo",
        "renderedCount": 7,
        "excludedPageIds": [],
    }
    export_id = UUID(export_data["exportId"])
    async with SessionFactory() as session:
        export_job = await session.scalar(
            select(Job).where(Job.type == "EXPORT", Job.project_id == UUID(project_id))
        )
        assert export_job is not None
        await _run_job(export_job.id)

    status = await client.get(f"/api/projects/{project_id}/exports/{export_id}")
    assert status.status_code == 200, status.text
    export_dto = status.json()["data"]
    assert export_dto["state"] == "SUCCEEDED"
    assert export_dto["artifact"] is not None
    assert export_dto["artifact"]["byteSize"] > 0
    assert export_dto["artifact"]["downloadPath"] == f"/api/exports/{export_id}/download"
    assert export_dto["validation"]["passed"] is True
    download = await client.get(f"/api/exports/{export_id}/download")
    assert download.status_code == 302
    assert download.headers["location"].startswith("/api/downloads/")

    pptx_bytes = await _export_bytes(export_id)
    assert pptx_bytes[:2] == b"PK"
    reopened = Presentation(BytesIO(pptx_bytes))
    assert len(reopened.slides) == 7

    for fmt, magic in (("HTML", b"<!doctype"), ("PDF", b"%PDF-")):
        version = await _version(client, project_id)
        created = await client.post(
            f"/api/projects/{project_id}/exports", json={"format": fmt}, headers=_headers(version)
        )
        assert created.status_code == 202, created.text
        current_export = UUID(created.json()["data"]["export"]["exportId"])
        async with SessionFactory() as session:
            job = await session.scalar(
                select(Job)
                .where(Job.type == "EXPORT", Job.project_id == UUID(project_id))
                .order_by(Job.created_at.desc())
                .limit(1)
            )
            assert job is not None
            assert job.payload.get("exportId") == str(current_export)
            await _run_job(job.id)
        one_export = await client.get(f"/api/projects/{project_id}/exports/{current_export}")
        assert one_export.json()["data"]["state"] == "SUCCEEDED"
        payload = await _export_bytes(current_export)
        assert payload.startswith(magic)
        assert len(payload) > 1000


async def test_stage_gates_and_outline_edits(client: httpx.AsyncClient):
    project_id = await _create_project(client, topic="Gate check")
    await _seed_profile(UUID(project_id), page_count=7)

    # Design before outline/style: style gate wins and returns 409.
    version = await _version(client, project_id)
    early_design = await client.post(
        f"/api/projects/{project_id}/design/generate", headers=_headers(version)
    )
    assert early_design.status_code == 409
    assert early_design.json()["error"]["messageKey"] == "error.gate.style_not_selected"

    # Plan before any outline exists.
    early_plan = await client.post(
        f"/api/projects/{project_id}/plan/generate", headers=_headers(version)
    )
    assert early_plan.status_code == 409
    assert early_plan.json()["error"]["messageKey"] == "error.gate.outline_missing"

    outline_job_id = await _generate_outline(client, project_id)
    await _run_job(UUID(outline_job_id))

    # Plan before confirmation.
    version = await _version(client, project_id)
    unconfirmed = await client.post(
        f"/api/projects/{project_id}/plan/generate", headers=_headers(version)
    )
    assert unconfirmed.status_code == 409
    assert unconfirmed.json()["error"]["messageKey"] == "error.gate.outline_unconfirmed"

    await _confirm_outline(client, project_id)

    # Style selection before plan completion.
    version = await _version(client, project_id)
    too_early = await client.put(
        f"/api/projects/{project_id}/style",
        json={"styleKey": "fresh-teal", "styleVersion": 1},
        headers=_headers(version),
    )
    assert too_early.status_code == 409
    assert too_early.json()["error"]["messageKey"] == "error.gate.plan_incomplete"

    # Empty instruction is rejected before a job exists.
    pages = await _pages(client, project_id)
    body_page = next(page for page in pages["pages"] if page["pageType"] == "BODY")
    version = await _version(client, project_id)
    empty = await client.post(
        f"/api/projects/{project_id}/pages/{body_page['pageId']}/plan/tweak",
        json={"instruction": "   "},
        headers=_headers(version),
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["messageKey"] == "error.validation.empty_instruction"

    # Export before design.
    version = await _version(client, project_id)
    export = await client.post(
        f"/api/projects/{project_id}/exports", json={"format": "PDF"}, headers=_headers(version)
    )
    assert export.status_code == 409
    assert export.json()["error"]["messageKey"] == "error.gate.design_incomplete"

    # Fixed pages are not deletable.
    cover = next(page for page in pages["pages"] if page["pageType"] == "COVER")
    version = await _version(client, project_id)
    delete_cover = await client.delete(
        f"/api/projects/{project_id}/outline/pages/{cover['pageId']}", headers=_headers(version)
    )
    assert delete_cover.status_code == 409
    assert delete_cover.json()["error"]["messageKey"] == "error.gate.fixed_page_not_deletable"

    # Title edit clears confirmation and only design is affected.
    version = await _version(client, project_id)
    title_edit = await client.patch(
        f"/api/projects/{project_id}/outline/pages/{cover['pageId']}",
        json={"title": "Renamed cover"},
        headers=_headers(version),
    )
    assert title_edit.status_code == 200, title_edit.text
    edited = title_edit.json()["data"]
    assert edited["outline"]["confirmed"] is False
    assert edited["outline"]["pages"][0]["title"] == "Renamed cover"
    assert edited["stale"]["cause"] == "OUTLINE_EDIT"
    assert edited["stale"]["affected"]["plan"] == []

    # Insert a body page: unconfirmed, new page, plan+design affected.
    version = await _version(client, project_id)
    insertion = await client.post(
        f"/api/projects/{project_id}/outline/pages",
        json={"sectionKey": "context", "title": "Appended note", "keyPoints": ["One"]},
        headers=_headers(version),
    )
    assert insertion.status_code == 200, insertion.text
    inserted = insertion.json()["data"]
    assert inserted["outline"]["counts"]["pages"] == 8
    assert inserted["outline"]["confirmed"] is False
    assert inserted["stale"]["affected"]["plan"] == [inserted["pageId"]]
    assert inserted["stale"]["affected"]["design"] == [inserted["pageId"]]

    # Move the inserted page within its section: design only.
    version = await _version(client, project_id)
    moved = await client.post(
        f"/api/projects/{project_id}/outline/pages/{inserted['pageId']}/move",
        json={"toSectionKey": "context", "toPosition": 1},
        headers=_headers(version),
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["data"]["stale"]["affected"]["plan"] == []

    # Cross-section move: plan and design.
    version = await _version(client, project_id)
    cross = await client.post(
        f"/api/projects/{project_id}/outline/pages/{inserted['pageId']}/move",
        json={"toSectionKey": "plan", "toPosition": 1},
        headers=_headers(version),
    )
    assert cross.status_code == 200, cross.text
    cross_data = cross.json()["data"]["stale"]
    assert cross_data["affected"]["plan"] == [inserted["pageId"]]
    assert inserted["pageId"] in cross_data["affected"]["design"]

    # Delete the inserted page: plan/design tombstoned and count restored.
    version = await _version(client, project_id)
    deleted = await client.delete(
        f"/api/projects/{project_id}/outline/pages/{inserted['pageId']}", headers=_headers(version)
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["outline"]["counts"]["pages"] == 7
    assert deleted.json()["data"]["stale"]["affected"]["plan"] == [inserted["pageId"]]

    # Auto-advance token issued by the snapshot is accepted.
    snapshot = await _snapshot(client, project_id)
    outline_stage = next(stage for stage in snapshot["stages"] if stage["stage"] == "OUTLINE")
    if outline_stage["advanceToken"]:
        version = await _version(client, project_id)
        advanced = await client.post(
            f"/api/projects/{project_id}/stages/advance",
            json={"fromStage": "OUTLINE", "advanceToken": outline_stage["advanceToken"]},
            headers=_headers(version),
        )
        assert advanced.status_code == 200, advanced.text
        assert advanced.json()["data"]["toStage"] == "PLAN"
