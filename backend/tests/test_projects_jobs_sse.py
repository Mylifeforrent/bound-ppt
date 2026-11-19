from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

# Environment MUST be set before any app module is imported: app.core.db creates
# the engine at import time from the cached Settings object.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="bound-ppt-api-test-"))
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_ROOT / 'test.db'}"
os.environ["STORAGE_LOCAL_ROOT"] = str(_TEST_ROOT / "storage")
os.environ["AUTO_CREATE_TABLES"] = "true"
os.environ["APP_ENV"] = "test"
os.environ["MODEL_PROVIDER"] = "stub"
os.environ["SEARCH_PROVIDER"] = "stub"

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import func, select  # noqa: E402
from starlette.requests import Request as StarletteRequest  # noqa: E402

from app.api.deps import CommandContext  # noqa: E402
from app.api.v1.events import _event_stream, stream_project_events  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import SessionFactory, init_db  # noqa: E402
from app.core.ids import new_id  # noqa: E402
from app.core.security import create_session, seed_pilot_user  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppUser, DomainEvent, Job, Project, RequirementsProfile  # noqa: E402


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


async def _create_project(client: httpx.AsyncClient, *, topic: str = "Quarterly review") -> tuple[dict, str]:
    key = str(uuid4())
    response = await client.post(
        "/api/projects",
        json={"topic": topic},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"], key


def _parse_sse(raw: str) -> dict:
    event = None
    data_lines: list[str] = []
    event_id = None
    for line in raw.splitlines():
        if not line:
            continue
        field, _, value = line.partition(":")
        value = value.lstrip(" ")
        if field == "event":
            event = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value
    return {"event": event, "id": event_id, "data": "\n".join(data_lines)}


async def _next_frame(stream, timeout: float = 5.0) -> str:
    return await asyncio.wait_for(stream.__anext__(), timeout=timeout)


async def test_create_project_and_snapshot(client: httpx.AsyncClient):
    response = await client.post(
        "/api/projects",
        json={"topic": "  Quarterly review  "},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    project = body["data"]["project"]
    snapshot = body["data"]["snapshot"]

    assert project["topic"] == "Quarterly review"
    assert project["name"] == "Quarterly review"
    assert project["mode"] == "FULLY_AUTOMATIC"
    assert project["status"] == "ACTIVE"
    assert project["stage"] == "INTAKE"
    assert project["version"] == 1
    assert project["epoch"] == 1
    assert snapshot["project"]["id"] == project["id"]
    assert snapshot["pointers"] == {
        "profileVersionId": None,
        "outlineVersionId": None,
        "styleSelectionId": None,
    }
    assert snapshot["sequence"] == 1
    assert body["meta"]["projectVersion"] == 1
    assert body["meta"]["sequence"] == 1

    snapshot_response = await client.get(f"/api/projects/{project['id']}/snapshot")
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot_body = snapshot_response.json()
    assert snapshot_body["data"]["sequence"] == 1
    assert snapshot_body["meta"]["projectVersion"] == 1
    assert snapshot_body["meta"]["sequence"] == 1

    empty = await client.post(
        "/api/projects",
        json={"topic": "   "},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert empty.status_code == 422
    assert empty.json()["error"]["messageKey"] == "error.validation.empty_topic"

    invalid_mode = await client.post(
        "/api/projects",
        json={"topic": "Topic", "mode": "NOT_A_MODE"},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert invalid_mode.status_code == 422
    assert invalid_mode.json()["error"]["category"] == "validation"


async def test_create_project_idempotent_replay(client: httpx.AsyncClient):
    key = str(uuid4())
    first = await client.post(
        "/api/projects",
        json={"topic": "Replay topic"},
        headers={"Idempotency-Key": key},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/projects",
        json={"topic": "Replay topic"},
        headers={"Idempotency-Key": key},
    )
    assert second.status_code == 201
    assert second.headers.get("idempotent-replay") == "true"
    assert second.json()["data"]["project"]["id"] == first.json()["data"]["project"]["id"]


async def test_patch_project_stale_version_and_topic_lock(client: httpx.AsyncClient):
    data, _ = await _create_project(client)
    project_id = data["project"]["id"]

    stale = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Renamed"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "99"},
    )
    assert stale.status_code == 409
    error = stale.json()["error"]
    assert error["category"] == "conflict"
    assert error["messageKey"] == "error.conflict.stale_version"
    assert error["details"]["currentVersion"] == 1

    renamed = await client.patch(
        f"/api/projects/{project_id}",
        json={"name": "Renamed", "topic": "New topic"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "1"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["data"]["project"]["name"] == "Renamed"
    assert renamed.json()["data"]["project"]["topic"] == "New topic"
    assert renamed.json()["data"]["project"]["version"] == 2

    async with SessionFactory() as session:
        project = await session.get(Project, UUID(project_id))
        project.stage = "RESEARCH"
        await session.commit()

    locked = await client.patch(
        f"/api/projects/{project_id}",
        json={"topic": "Another topic"},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "2"},
    )
    assert locked.status_code == 409
    assert locked.json()["error"]["messageKey"] == "error.gate.topic_locked"


async def test_restart_resets_state_and_cancels_jobs(client: httpx.AsyncClient):
    data, _ = await _create_project(client)
    project_id = UUID(data["project"]["id"])

    job_id = new_id()
    async with SessionFactory() as session:
        session.add(
            RequirementsProfile(
                id=new_id(),
                project_id=project_id,
                version=1,
                audience="exec",
                goal="review",
                style_mood="calm",
                page_count=8,
                materials_summary={},
                web_scope={},
                web_skipped=True,
                content_strategy="material_first",
                source_refs=[],
                input_fingerprint="fingerprint",
            )
        )
        session.add(
            Job(
                id=job_id,
                project_id=project_id,
                type="OUTLINE",
                operation_key=f"outline:{project_id}",
                active_operation_key=f"outline:{project_id}",
                state="QUEUED",
                payload={"epoch": 1},
                max_attempts=3,
            )
        )
        await session.commit()

    response = await client.post(
        f"/api/projects/{project_id}/restart",
        json={"confirm": True},
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "1"},
    )
    assert response.status_code == 202, response.text
    body = response.json()["data"]
    assert body["project"]["stage"] == "INTAKE"
    assert body["project"]["epoch"] == 2
    assert body["project"]["version"] == 2
    assert str(job_id) in body["cancelledJobIds"]
    assert body["snapshot"]["pointers"] == {
        "profileVersionId": None,
        "outlineVersionId": None,
        "styleSelectionId": None,
    }
    assert body["snapshot"]["sequence"] >= 4

    async with SessionFactory() as session:
        profile_count = await session.scalar(
            select(func.count()).select_from(RequirementsProfile).where(RequirementsProfile.project_id == project_id)
        )
        job = await session.get(Job, job_id)
        events = (
            await session.scalars(
                select(DomainEvent).where(DomainEvent.project_id == project_id).order_by(DomainEvent.sequence)
            )
        ).all()
        assert profile_count == 0
        assert job.state == "CANCELLED"
        assert job.completed_at is not None
        assert job.active_operation_key is None
        assert [e.type for e in events][:4] == [
            "projectCreated",
            "jobCancelled",
            "stageStateChanged",
            "staleChanged",
        ]
        assert [e.sequence for e in events] == list(range(1, len(events) + 1))


async def test_delete_project_returns_202_then_404(client: httpx.AsyncClient):
    data, _ = await _create_project(client)
    project_id = data["project"]["id"]

    deleted = await client.delete(
        f"/api/projects/{project_id}",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "1"},
    )
    assert deleted.status_code == 202, deleted.text
    body = deleted.json()["data"]
    assert body["projectId"] == project_id
    assert body["status"] == "DELETING"
    assert body["jobId"]

    async with SessionFactory() as session:
        job = await session.get(Job, UUID(body["jobId"]))
        assert job is not None
        assert job.type == "DELETE_PROJECT"
        assert job.state == "QUEUED"

    missing = await client.get(f"/api/projects/{project_id}/snapshot")
    assert missing.status_code == 404
    assert missing.json()["error"]["messageKey"] == "error.not_found.project"

    # Run the registered maintenance handler in-process (the test does not start
    # the background runner) and verify the tombstone/content purge.
    import app.worker.handlers  # noqa: F401
    from app.ingest.search import search
    from app.llm.gateway import gateway
    from app.storage import storage
    from app.worker.runner import HANDLERS, JobContext

    async with SessionFactory() as session:
        job = await session.get(Job, UUID(body["jobId"]))
        job.state = "RUNNING"
        job.attempt_count = 1
        job.fencing_token = 1
        await session.flush()
        ctx = JobContext(
            session=session,
            job=job,
            attempt_id=new_id(),
            fencing_token=1,
            settings=get_settings(),
            gateway=gateway,
            search=search,
            storage=storage,
            worker_id="test-worker",
        )
        await HANDLERS["DELETE_PROJECT"](ctx)
        await session.commit()

        project = await session.get(Project, UUID(project_id))
        assert project.status == "DELETED"
        assert project.deleted_at is not None
        assert project.name == ""
        assert project.topic == ""
        event_count = await session.scalar(
            select(func.count()).select_from(DomainEvent).where(DomainEvent.project_id == UUID(project_id))
        )
        assert event_count == 0


async def test_job_cancel_is_idempotent_and_bumps_once(client: httpx.AsyncClient):
    data, _ = await _create_project(client)
    project_id = UUID(data["project"]["id"])
    queued_id = new_id()
    running_id = new_id()

    async with SessionFactory() as session:
        session.add(
            Job(
                id=queued_id,
                project_id=project_id,
                type="OUTLINE",
                operation_key=f"outline:{project_id}",
                active_operation_key=f"outline:{project_id}",
                state="QUEUED",
                payload={"epoch": 1},
                max_attempts=3,
            )
        )
        session.add(
            Job(
                id=running_id,
                project_id=project_id,
                type="PROFILE",
                operation_key=f"profile:{project_id}",
                active_operation_key=f"profile:{project_id}",
                state="RUNNING",
                payload={"epoch": 1},
                max_attempts=3,
                attempt_count=1,
            )
        )
        await session.commit()

    cancelled = await client.post(
        f"/api/projects/{project_id}/jobs/{queued_id}/cancel",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "1"},
    )
    assert cancelled.status_code == 200, cancelled.text
    job = cancelled.json()["data"]["job"]
    assert job["state"] == "CANCELLED"
    assert job["completedAt"] is not None
    assert cancelled.json()["meta"]["projectVersion"] == 2

    polled = await client.get(f"/api/projects/{project_id}/jobs/{queued_id}")
    assert polled.status_code == 200
    assert polled.json()["data"]["state"] == "CANCELLED"

    requested = await client.post(
        f"/api/projects/{project_id}/jobs/{running_id}/cancel",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "2"},
    )
    assert requested.status_code == 200
    running = requested.json()["data"]["job"]
    assert running["state"] == "RUNNING"
    assert running["cancelRequested"] is True
    assert requested.json()["meta"]["projectVersion"] == 3

    repeated = await client.post(
        f"/api/projects/{project_id}/jobs/{queued_id}/cancel",
        headers={"Idempotency-Key": str(uuid4()), "X-Expected-Version": "3"},
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["job"]["state"] == "CANCELLED"
    assert repeated.json()["meta"]["projectVersion"] == 3


async def test_sse_snapshot_and_domain_frames(client: httpx.AsyncClient):
    data, _ = await _create_project(client, topic="SSE topic")
    project_id = UUID(data["project"]["id"])

    # Direct generator read: the ASGI transport buffers a response to completion,
    # so an endlessly streaming endpoint cannot be consumed through httpx here.
    stream = _event_stream(project_id, None)
    try:
        raw = await _next_frame(stream)
    finally:
        await stream.aclose()
    frame = _parse_sse(raw)
    assert frame["event"] == "snapshot"
    assert frame["id"] == "1"
    snapshot_data = json.loads(frame["data"])
    assert snapshot_data["sequence"] == 1
    assert snapshot_data["snapshot"]["project"]["id"] == str(project_id)

    replay_stream = _event_stream(project_id, 0)
    try:
        raw = await _next_frame(replay_stream)
    finally:
        await replay_stream.aclose()
    domain = _parse_sse(raw)
    assert domain["event"] == "domain"
    assert domain["id"] == "1"
    domain_data = json.loads(domain["data"])
    assert domain_data["type"] == "projectCreated"
    assert domain_data["projectId"] == str(project_id)
    assert domain_data["payload"]["stage"] == "INTAKE"
    assert domain_data["payload"]["mode"] == "FULLY_AUTOMATIC"

    # Response headers required by the SSE contract.
    async with SessionFactory() as session:
        user = await session.scalar(
            select(AppUser).where(AppUser.email == get_settings().pilot_email)
        )
        ctx = CommandContext(
            request_id="test-request",
            trace_id="test-trace",
            idempotency_key=None,
            expected_version=None,
            user=user,
        )
        request = StarletteRequest(
            {
                "type": "http",
                "method": "GET",
                "path": f"/api/projects/{project_id}/events",
                "query_string": b"",
                "headers": [],
                "server": ("test", 80),
                "client": ("test", 1234),
                "scheme": "http",
                "root_path": "",
                "http_version": "1.1",
            }
        )
        response = await stream_project_events(
            project_id,
            request,
            cursor=None,
            ctx=ctx,
            session=session,
        )
        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["connection"] == "keep-alive"
        assert response.headers["x-accel-buffering"] == "no"
        await response.body_iterator.aclose()
