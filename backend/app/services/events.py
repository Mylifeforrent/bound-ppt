from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import UUID


class EventBus:
    """In-process fan-out for committed domain events and ephemeral deltas.

    Durable replay lives in `domain_event`; this bus only serves live SSE subscribers.
    """

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, project_id: UUID) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers[project_id].add(queue)
        return queue

    def unsubscribe(self, project_id: UUID, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[project_id].discard(queue)
        if not self._subscribers[project_id]:
            self._subscribers.pop(project_id, None)

    def publish(self, project_id: UUID, frame: dict[str, Any]) -> None:
        for queue in list(self._subscribers.get(project_id, ())):
            try:
                queue.put_nowait(frame)
            except asyncio.QueueFull:
                self._subscribers[project_id].discard(queue)

    def publish_ephemeral(self, project_id: UUID, payload: dict[str, Any]) -> None:
        self.publish(project_id, {"_frame": "ephemeral", "payload": payload})


bus = EventBus()

# Re-exported here so callers have one import surface for the event system.
from app.services.event_appender import EventService  # noqa: E402

events = EventService()
