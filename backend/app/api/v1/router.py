from fastapi import APIRouter

from app.api.v1 import (
    auth,
    design,
    events,
    exports,
    jobs,
    materials,
    outline,
    pages,
    plan,
    projects,
    research,
    styles,
    system,
)

api_router = APIRouter()
for module in (
    system,
    auth,
    projects,
    materials,
    research,
    outline,
    pages,
    plan,
    design,
    styles,
    exports,
    jobs,
    events,
):
    api_router.include_router(module.router)
