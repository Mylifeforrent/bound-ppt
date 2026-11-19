from __future__ import annotations

from collections.abc import AsyncIterator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Base

settings = get_settings()

connect_args: dict[str, object] = {}
engine_kwargs: dict[str, object] = {"pool_pre_ping": True}
if settings.is_sqlite:
    connect_args = {"check_same_thread": False}
    engine_kwargs = {}

engine = create_async_engine(settings.database_url, connect_args=connect_args, **engine_kwargs)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    await engine.dispose()


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        yield session


def _after_commit(session: sa.orm.Session) -> None:
    from app.services.events import bus

    pending = session.info.pop("_domain_events", [])
    for project_id, frame in pending:
        bus.publish(project_id, frame)


def _after_rollback(session: sa.orm.Session) -> None:
    session.info.pop("_domain_events", [])


sa.event.listen(AsyncSession.sync_session_class, "after_commit", _after_commit)
sa.event.listen(AsyncSession.sync_session_class, "after_rollback", _after_rollback)
