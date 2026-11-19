from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import conflict, validation
from app.core.ids import digest_json, new_id, utcnow
from app.models import IdempotencyRecord, Project


def request_hash(payload: Any) -> str:
    return digest_json(payload)


async def check_replay(
    session: AsyncSession, *, scope_key: str, key: str, payload_hash: str
) -> IdempotencyRecord | None:
    row = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.scope_key == scope_key,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if row is None:
        return None
    if row.request_hash != payload_hash:
        raise validation("error.validation.idempotency_key_reused")
    if row.state == "IN_PROGRESS":
        raise conflict("error.conflict.command_in_progress")
    return row


async def begin_command(
    session: AsyncSession,
    *,
    scope_key: str,
    key: str,
    payload: Any,
    project: Project | None = None,
    expected_version: int | None = None,
) -> tuple[IdempotencyRecord | None, IdempotencyRecord | None]:
    """Return (replay_record, new_record).

    A replay record means the caller must return the stored response without
    executing the command. A new record is created for first-time intents.
    """
    if project is not None and expected_version is not None and project.version != expected_version:
        raise conflict("error.conflict.stale_version", {"currentVersion": project.version})
    ph = request_hash(payload)
    replay = await check_replay(session, scope_key=scope_key, key=key, payload_hash=ph)
    if replay is not None and replay.state == "COMPLETED":
        return replay, None
    record = IdempotencyRecord(
        id=new_id(),
        project_id=project.id if project else None,
        scope_key=scope_key,
        idempotency_key=key,
        request_hash=ph,
        state="IN_PROGRESS",
        created_at=utcnow(),
        expires_at=utcnow() + timedelta(days=1),
    )
    session.add(record)
    await session.flush()
    return None, record


def finish_command(
    record: IdempotencyRecord | None,
    *,
    status_code: int,
    response: Any,
    resource_type: str | None = None,
    resource_id: Any = None,
) -> None:
    if record is None:
        return
    record.state = "COMPLETED"
    record.status_code = status_code
    record.response_json = response
    record.resource_type = resource_type
    record.resource_id = resource_id


def bump_project(project: Project) -> int:
    project.version += 1
    project.updated_at = utcnow()
    return project.version


def cleanup_expired(session: AsyncSession) -> None:
    # Called opportunistically; retention value is configuration-owned.
    pass
