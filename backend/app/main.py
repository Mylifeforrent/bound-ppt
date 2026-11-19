from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import REPO_ROOT, get_settings
from app.core.db import SessionFactory, dispose_db, init_db
from app.core.errors import AppError
from app.core.ids import iso, utcnow
from app.core.security import seed_pilot_user
from app.worker.runner import runner

logger = logging.getLogger("bound_ppt")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level)),
    )
    await init_db()
    async with SessionFactory() as session:
        await seed_pilot_user(session)
        await session.commit()
    import app.worker.handlers  # noqa: F401  (registers handlers)

    await runner.start()
    yield
    await runner.stop()
    await dispose_db()


app = FastAPI(
    title="Bound PPT API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.trace_id = request.headers.get("x-trace-id") or uuid4().hex
    response = await call_next(request)
    response.headers.setdefault("X-Request-Id", request.state.request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/api/") and not request.url.path.endswith("/events"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    payload = {
        "ok": False,
        "error": {
            "category": exc.category,
            "retryable": exc.retryable,
            "messageKey": exc.message_key,
            "details": exc.details,
            "requestId": getattr(request.state, "request_id", ""),
            "traceId": getattr(request.state, "trace_id", ""),
            "retryAfterMs": None,
        },
    }
    headers = {"Cache-Control": "no-store", **exc.headers}
    return JSONResponse(status_code=exc.http_status, content=payload, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    fields = []
    for err in exc.errors():
        loc = [str(part) for part in err.get("loc", []) if part != "body"]
        fields.append(".".join(loc))
    payload = {
        "ok": False,
        "error": {
            "category": "validation",
            "retryable": False,
            "messageKey": "error.validation.invalid_request",
            "details": {"fields": fields[:12]},
            "requestId": getattr(request.state, "request_id", ""),
            "traceId": getattr(request.state, "trace_id", ""),
        },
    }
    return JSONResponse(status_code=422, content=payload, headers={"Cache-Control": "no-store"})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("unhandled error request_id=%s path=%s", getattr(request.state, "request_id", ""), request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": {
                "category": "internal",
                "retryable": True,
                "messageKey": "error.internal.unexpected",
                "details": {},
                "requestId": getattr(request.state, "request_id", ""),
                "traceId": getattr(request.state, "trace_id", ""),
            },
        },
        headers={"Cache-Control": "no-store"},
    )


app.include_router(api_router)

# Serve the built SPA when it exists (production-style single process).
dist = REPO_ROOT / "frontend" / "dist"
if (dist / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    if full_path.startswith(("api/", "openapi.json", "docs", "redoc")):
        return JSONResponse(status_code=404, content={"ok": False, "error": {"category": "not_found"}})
    index = dist / "index.html"
    candidate = dist / full_path if full_path else None
    if candidate and candidate.is_file() and dist in candidate.resolve().parents:
        return FileResponse(candidate)
    if index.is_file():
        return FileResponse(index)
    return JSONResponse(
        status_code=200,
        content={
            "service": "bound-ppt-api",
            "time": iso(utcnow()),
            "hint": "Frontend dev server: npm run dev in frontend/",
        },
    )
