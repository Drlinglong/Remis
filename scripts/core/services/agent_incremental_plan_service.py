"""Connect read-only incremental comparisons to approval-owned Agent plans."""
from fastapi import HTTPException

from scripts.core.services.agent_incremental_preview_service import build_incremental_preview
from scripts.schemas.agent import AgentPlanResponse
from scripts.shared.services import project_manager


async def preview_for_request(request):
    preview = await build_incremental_preview(
        request.project_id, request.custom_source_path,
        [getattr(code, "value", code) for code in request.target_lang_codes],
        project_manager=project_manager,
    )
    if (request.expected_preview_fingerprint
            and request.expected_preview_fingerprint != preview["fingerprint"]):
        raise ValueError("Incremental preview is stale; inspect the source and baseline again")
    return preview


def bind_incremental_preview(plan, preview):
    plan["execution_args"].update(
        custom_source_path=preview["source_path"],
        incremental_preview=preview,
    )
    plan["inspection"] = {**plan.get("inspection", {}),
                          "source_path": preview["source_path"],
                          "source_language": preview["source_language"]}


def create_incremental_dry_plan(request, preview, registry):
    args = request.model_dump(mode="json")
    args.update(custom_source_path=preview["source_path"], incremental_preview=preview)
    summary = "Read-only incremental entry comparison. No provider, model call or output write."
    record = registry.create_plan(project_id=request.project_id, execution_args=args,
                                  dry_run=True, summary=summary)
    return AgentPlanResponse(
        plan_id=record["plan_id"], status="ready", project_id=request.project_id,
        dry_run=True, requires_approval=False,
        risk={"writes_output": False, "may_use_paid_api": False}, summary=summary,
        allowed_actions=["start_dry_run"],
        translation={"workflow": "incremental", "incremental_preview": preview},
        expires_at=record["expires_at"],
    )


async def require_current_preview(args):
    expected = args.get("incremental_preview")
    if not expected:
        raise HTTPException(409, detail={"code": "incremental_preview_required",
                                        "message": "Create a fresh incremental Agent plan"})
    try:
        actual = await build_incremental_preview(
            args["project_id"], args.get("custom_source_path"), args["target_lang_codes"],
            project_manager=project_manager,
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, detail={"code": "incremental_preview_stale", "message": str(exc)}) from exc
    if actual["fingerprint"] != expected["fingerprint"]:
        raise HTTPException(409, detail={"code": "incremental_preview_stale",
                                        "message": "Source or archive changed; create and review a new plan"})
