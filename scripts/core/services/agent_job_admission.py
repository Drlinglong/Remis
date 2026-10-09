"""Bind an Agent API plan to the translation task it just queued."""

from __future__ import annotations

from typing import Any

from scripts.shared import task_state
from scripts.shared.task_admission import rollback_unstarted_task


def bind_agent_translation_job(
    *,
    job_id: str,
    project_id: str,
    plan_id: str,
    execution_args: dict[str, Any],
    registry: Any,
) -> None:
    """Record Agent ownership; on failure release the queued task and the plan.

    The worker is queued on the route's BackgroundTasks, which never run when
    the route raises, so a failure here must not leave the task holding the
    project write key.
    """
    kind = "incremental_translation" if execution_args.get("workflow") == "incremental" else "translation"
    try:
        with rollback_unstarted_task(job_id):
            task_state.update_task(
                job_id,
                fields={
                    "project_id": project_id,
                    "agent_job_kind": kind,
                    "created_by": {"type": "remis_agent", "label": "Remis Agent"},
                    "idempotency_key": plan_id,
                },
            )
            registry.record_job(
                job_id=job_id,
                project_id=project_id,
                plan_id=plan_id,
                kind=kind,
                execution_args=execution_args,
            )
    except BaseException:
        registry.release_plan(plan_id)
        raise
