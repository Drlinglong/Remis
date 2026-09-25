"""Agent task dispatch reuses the existing initial and incremental runners."""
import uuid
from scripts.schemas.translation import InitialTranslationRequest


async def create_readiness_job(plan, plan_id, *, registry, project_manager, task_state):
    args = plan["execution_args"]
    project = await project_manager.get_project(plan["project_id"])
    files = await project_manager.get_project_files(plan["project_id"])
    job_id = f"job_{uuid.uuid4().hex}"
    task_state.create_task(job_id, status="completed", log_message="Agent dry-run readiness check completed.",
        fields={"kind": "dry_run", "project_id": plan["project_id"],
                "created_by": {"type": "remis_agent", "label": "Remis Agent"}, "idempotency_key": plan_id})
    task_state.init_progress(job_id, {"total": len(files), "current": len(files), "percent": 100,
                                     "stage": "Readiness check completed"})
    task_state.update_task(job_id, summary={
        "project_name": (project or {}).get("name"), "file_count": len(files),
        "would_use_provider": args.get("api_provider"), "would_use_model": args.get("model"),
        "translation_context_mode": args.get("translation_context_mode"),
        "workflow": args.get("workflow", "initial"), "diff_executed": False,
    }, fields={"project_id": plan["project_id"], "agent_job_kind": "dry_run", "output_dirs": []})
    registry.record_job(job_id=job_id, project_id=plan["project_id"], plan_id=plan_id,
                        kind="dry_run", execution_args=args)
    return job_id


async def dispatch_translation(args, plan_id, background_tasks, initial_starter):
    if args.get("workflow") == "incremental":
        from scripts.routers.projects import run_incremental_update
        from scripts.schemas.project import IncrementalUpdateRequest
        return await run_incremental_update(args["project_id"],
            IncrementalUpdateRequest(**{**args, "dry_run": False, "use_resume": False}), background_tasks)
    return await initial_starter(InitialTranslationRequest(**{**args, "idempotency_key": plan_id}), background_tasks)
