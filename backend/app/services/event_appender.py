from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import iso, new_id, utcnow
from app.models import DomainEvent, ProjectEventCounter


class EventService:
    async def append(
        self,
        session: AsyncSession,
        project_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        content_free: bool = True,
    ) -> DomainEvent:
        counter = await session.get(ProjectEventCounter, project_id)
        if counter is None:
            counter = ProjectEventCounter(project_id=project_id, last_sequence=0)
            session.add(counter)
            await session.flush()
        counter.last_sequence += 1
        event = DomainEvent(
            id=new_id(),
            project_id=project_id,
            sequence=counter.last_sequence,
            type=event_type,
            schema_version=1,
            payload=payload if content_free else payload,
            request_id=request_id,
            trace_id=trace_id,
            created_at=utcnow(),
        )
        session.add(event)
        await session.flush()
        frame = self.frame_for(event)
        session.info.setdefault("_domain_events", []).append((project_id, frame))
        return event

    @staticmethod
    def frame_for(event: DomainEvent) -> dict[str, Any]:
        return {
            "_frame": "domain",
            "id": event.sequence,
            "data": {
                "eventId": str(event.id),
                "sequence": event.sequence,
                "projectId": str(event.project_id),
                "type": event.type,
                "schemaVersion": event.schema_version,
                "occurredAt": iso(event.created_at),
                "payload": event.payload,
            },
        }

    async def replay(self, session: AsyncSession, project_id: UUID, cursor: int) -> list[DomainEvent]:
        result = await session.scalars(
            select(DomainEvent)
            .where(DomainEvent.project_id == project_id, DomainEvent.sequence > cursor)
            .order_by(DomainEvent.sequence)
        )
        return list(result)

    async def latest_sequence(self, session: AsyncSession, project_id: UUID) -> int:
        counter = await session.get(ProjectEventCounter, project_id)
        return counter.last_sequence if counter else 0


events = EventService()
