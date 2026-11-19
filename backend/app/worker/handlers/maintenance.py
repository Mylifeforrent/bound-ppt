"""Maintenance job handlers (DELETE_PROJECT).

Imported by app.worker.handlers.
"""

from __future__ import annotations

from app.domain.enums import JobType, ProjectStatus
from app.models import Project
from app.services.projects import purge_project
from app.worker.runner import JobContext, register


@register(JobType.DELETE_PROJECT)
async def delete_project(ctx: JobContext) -> None:
    """Delete object content and derived rows, then write the project tombstone.

    The runner commits the handler transaction together with the terminal job state.
    A deleted project never emits an event; any pre-existing event rows are purged.
    """
    project = await ctx.session.get(Project, ctx.project_id)
    if project is None or project.status == ProjectStatus.DELETED.value:
        return
    await purge_project(ctx.session, project, ctx.storage)
