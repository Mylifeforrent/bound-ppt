from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CommandContext, command_context, load_owned_project
from app.core.db import SessionFactory, get_session
from app.core.ids import iso, utcnow
from app.domain.enums import ProjectStatus
from app.models import Project
from app.services.events import bus, events
from app.services.state import build_snapshot

router = APIRouter()

POLL_TIMEOUT_SECONDS = 5.0
HEARTBEAT_INTERVAL_SECONDS = 15.0


def _parse_cursor(raw: str | None) -> int | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value.isdigit():
        return None
    return int(value)


def _sse(event: str, data: dict[str, Any], *, event_id: int | None = None) -> str:
    lines = [f"event: {event}"]
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append("data: " + json.dumps(data, separators=(",", ":"), ensure_ascii=False))
    return "\n".join(lines) + "\n\n"


async def _replay_after(project_id: UUID, cursor: int) -> list[dict[str, Any]]:
    """Read durable frames newer than cursor using a fresh short-lived session."""
    async with SessionFactory() as session:
        rows = await events.replay(session, project_id, cursor)
        return [events.frame_for(row) for row in rows]


async def _event_stream(project_id: UUID, cursor: int | None) -> AsyncIterator[str]:
    # Subscribe before the replay/snapshot read so no live committed frame can be missed.
    queue = bus.subscribe(project_id)
    last_sent = cursor
    try:
        if last_sent is None:
            async with SessionFactory() as session:
                project = await session.get(Project, project_id)
                if project is None or project.status == ProjectStatus.DELETED.value:
                    return
                snapshot = await build_snapshot(session, project)
            last_sent = snapshot.sequence
            yield _sse(
                "snapshot",
                {
                    "snapshot": snapshot.model_dump(mode="json", by_alias=True),
                    "sequence": last_sent,
                },
                event_id=last_sent,
            )
        else:
            for frame in await _replay_after(project_id, last_sent):
                sequence = int(frame["id"])
                if sequence <= last_sent:
                    continue
                yield _sse("domain", frame["data"], event_id=sequence)
                last_sent = sequence

        last_heartbeat = time.monotonic()
        last_poll = last_heartbeat
        while True:
            frame: dict[str, Any] | None = None
            try:
                frame = await asyncio.wait_for(queue.get(), timeout=POLL_TIMEOUT_SECONDS)
            except TimeoutError:
                frame = None

            if frame is not None:
                kind = frame.get("_frame")
                if kind == "domain":
                    sequence = int(frame.get("id") or 0)
                    if sequence > last_sent:
                        yield _sse("domain", frame.get("data") or {}, event_id=sequence)
                        last_sent = sequence
                elif kind == "ephemeral":
                    yield _sse("ephemeral", frame.get("payload") or {})

            now = time.monotonic()
            if frame is None or now - last_poll >= POLL_TIMEOUT_SECONDS:
                # Defensive durable poll: covers a lost bus frame or a subscriber
                # that attached exactly as a commit completed.
                for durable in await _replay_after(project_id, last_sent):
                    sequence = int(durable["id"])
                    if sequence <= last_sent:
                        continue
                    yield _sse("domain", durable["data"], event_id=sequence)
                    last_sent = sequence
                last_poll = now

            if now - last_heartbeat >= HEARTBEAT_INTERVAL_SECONDS:
                yield _sse("heartbeat", {"serverTime": iso(utcnow())})
                last_heartbeat = time.monotonic()
    except asyncio.CancelledError:
        return
    finally:
        bus.unsubscribe(project_id, queue)


@router.get("/api/projects/{project_id}/events")
async def stream_project_events(
    project_id: UUID,
    request: Request,
    cursor: str | None = Query(default=None),
    ctx: CommandContext = Depends(command_context),
    session: AsyncSession = Depends(get_session),
):
    project = await load_owned_project(session, project_id, ctx.user)
    # Last-Event-ID is only a fallback when the cursor query parameter is absent.
    if cursor is None:
        start_cursor = _parse_cursor(request.headers.get("last-event-id"))
    else:
        start_cursor = _parse_cursor(cursor)
    return StreamingResponse(
        _event_stream(project.id, start_cursor),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
