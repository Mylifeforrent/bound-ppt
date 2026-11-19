from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import envelope, get_current_user, to_jsonable
from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import (
    SESSION_COOKIE,
    create_session,
    verify_password,
)
from app.models import AppUser, BillingAccount
from app.schemas.dto import AccountDTO, LoginRequest, UserDTO

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(payload: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    user = await session.scalar(select(AppUser).where(AppUser.email == payload.email.strip().lower()))
    if user is None or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise AppError("forbidden", "error.auth.invalid_credentials", http_status=401)
    token, _ = await create_session(session, user.id)
    await session.commit()
    resp = envelope(
        {"user": to_jsonable(UserDTO(id=user.id, email=user.email, name=user.name, role=user.role))},
        request=request,
    )
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
        max_age=7 * 24 * 3600,
    )
    return resp


@router.post("/logout")
async def logout(request: Request):
    resp = envelope({"loggedOut": True}, request=request)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/me")
async def me(user: AppUser = Depends(get_current_user), session: AsyncSession = Depends(get_session), request: Request = None):
    account = await session.get(BillingAccount, user.account_id) if user.account_id else None
    return envelope(
        {
            "user": UserDTO(id=user.id, email=user.email, name=user.name, role=user.role),
            "account": (
                AccountDTO(
                    id=account.id, name=account.name, plan=account.plan, billing_status=account.billing_status
                )
                if account
                else None
            ),
        },
        request=request,
    )
