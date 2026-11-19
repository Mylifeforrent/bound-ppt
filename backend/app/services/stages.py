from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project
from app.services import state
from app.services.events import events


async def emit_stage_state(session: AsyncSession, project: Project, previous_status: str = "IN_PROGRESS") -> None:
    """Append a stageStateChanged event derived from current server state.

    Call after bumping project.version and before commit.
    """
    snapshot = await state.build_snapshot(session, project)
    stage_state = next((s for s in snapshot.stages if s.stage == project.stage), None)
    if stage_state is None:
        return
    await events.append(
        session,
        project.id,
        "stageStateChanged",
        {
            "stage": stage_state.stage,
            "status": stage_state.status,
            "previousStatus": previous_status,
            "reachable": stage_state.reachable,
            "staleReasons": stage_state.stale_reasons,
            "projectVersion": project.version,
        },
    )


async def emit_stale_changed(
    session: AsyncSession,
    project: Project,
    *,
    from_stage: str,
    cause: str,
    affected_plan: list,
    affected_design: list,
    changed_pages: int | None = None,
) -> None:
    summary = state.make_stale_summary(
        project,
        cause,
        plan_pages=affected_plan,
        design_pages=affected_design,
        changed_pages=changed_pages,
    )
    await events.append(
        session,
        project.id,
        "staleChanged",
        {
            "fromStage": from_stage,
            "cause": cause,
            "affectedPageIds": [str(p) for p in affected_plan + affected_design],
            "affectedPages": len(set(affected_plan) | set(affected_design)),
            "rerunPages": summary.rerun["plan"] + summary.rerun["design"],
            "cascadeRatio": summary.cascade_ratio,
            "projectVersion": project.version,
        },
    )
