from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.core.db import SessionFactory, dispose_db, init_db
from app.core.ids import new_id, utcnow
from app.core.security import hash_password
from app.models import AppUser, BillingAccount


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create or update a Bound PPT user.")
    parser.add_argument("--email", required=True, help="User email (login identifier).")
    parser.add_argument("--password", required=True, help="Plain-text password to hash and store.")
    parser.add_argument("--name", default=None, help="Display name.")
    return parser


async def create_user(email: str, password: str, name: str | None = None) -> tuple[str, str]:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise SystemExit("--email must not be empty")
    if not password:
        raise SystemExit("--password must not be empty")

    await init_db()
    try:
        async with SessionFactory() as session:
            user = await session.scalar(select(AppUser).where(AppUser.email == normalized_email))
            if user is None:
                account = BillingAccount(
                    id=new_id(),
                    name=name or normalized_email,
                    plan="pilot",
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                session.add(account)
                await session.flush()
                user = AppUser(
                    id=new_id(),
                    account_id=account.id,
                    email=normalized_email,
                    name=name,
                    role="OWNER",
                    password_hash=hash_password(password),
                    created_at=utcnow(),
                    updated_at=utcnow(),
                )
                session.add(user)
            else:
                user.password_hash = hash_password(password)
                if name:
                    user.name = name
                if user.account_id is None:
                    account = BillingAccount(
                        id=new_id(),
                        name=name or normalized_email,
                        plan="pilot",
                        created_at=utcnow(),
                        updated_at=utcnow(),
                    )
                    session.add(account)
                    await session.flush()
                    user.account_id = account.id
            await session.commit()
            return str(user.id), user.email
    finally:
        await dispose_db()


async def main() -> None:
    args = _build_parser().parse_args()
    user_id, email = await create_user(args.email, args.password, args.name)
    print(f"id={user_id} email={email}")


if __name__ == "__main__":
    asyncio.run(main())
