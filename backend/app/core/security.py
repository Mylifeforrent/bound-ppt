from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.ids import new_id, random_token, token_hash
from app.models import AppUser, Session

password_hash = PasswordHash.recommended()

SESSION_COOKIE = "bound_session"


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except Exception:  # noqa: BLE001
        return False


async def create_session(session: AsyncSession, user_id: UUID) -> tuple[str, Session]:
    token = random_token(32)
    row = Session(
        id=new_id(),
        session_token=token_hash(token),
        user_id=user_id,
        expires=datetime.now(UTC) + timedelta(days=7),
        created_at=datetime.now(UTC),
    )
    session.add(row)
    await session.flush()
    return token, row


async def resolve_session(session: AsyncSession, token: str) -> AppUser | None:
    if not token:
        return None
    row = await session.scalar(
        select(Session).where(Session.session_token == token_hash(token), Session.expires > datetime.now(UTC))
    )
    if row is None:
        return None
    return await session.get(AppUser, row.user_id)


async def seed_pilot_user(session: AsyncSession) -> AppUser:
    from app.models import BillingAccount

    settings = get_settings()
    existing = await session.scalar(select(AppUser).where(AppUser.email == settings.pilot_email))
    if existing:
        if not existing.password_hash:
            existing.password_hash = hash_password(settings.pilot_password)
        return existing
    account = BillingAccount(
        id=new_id(),
        name="Pilot account",
        plan="pilot",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(account)
    await session.flush()
    user = AppUser(
        id=new_id(),
        account_id=account.id,
        email=settings.pilot_email,
        name=settings.pilot_name,
        role="OWNER",
        password_hash=hash_password(settings.pilot_password),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(user)
    await session.flush()
    return user
