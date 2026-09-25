"""Focused orchestration for Agent-owned initial and incremental translation plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from scripts.schemas.agent import AgentJobPlanRequest, AgentPlanResponse
from scripts.schemas.agent_language import language_plan_details
from scripts.core.services.translation_context_readiness_service import TranslationContextModeResolution
from scripts.core.services.translation_recovery_service import TranslationRecoveryService


@dataclass(frozen=True)
class AgentTranslationPlanError(RuntimeError):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


def resolve_agent_retry_checkpoint(
    repository: Any, *, task_id: str, project_id: str,
) -> dict[str, Any]:
    """Return the persisted checkpoint lineage required by an Agent retry."""

    if repository is None:
        raise ValueError("Task persistence is unavailable for checkpoint retry")
    recovery_service = TranslationRecoveryService(repository)
    recovery_service.require_resumable_identity(task_id)
    checkpoint = recovery_service.inspect(project_id).get("checkpoint") or {}
    checkpoint_revision = checkpoint.get("revision")
    if checkpoint_revision is None:
        raise ValueError("Checkpoint revision is unavailable; refresh recovery before retrying")
    return {
        "use_resume": True,
        "resume_from_task_id": task_id,
        "expected_checkpoint_revision": int(checkpoint_revision),
    }


async def _resolve_agent_context(request, execution_args, plan, readiness_service):
    resolver = getattr(readiness_service, "resolve_mode", None)
    resolution = None
    if callable(resolver):
        resolution = await resolver(
            request.project_id,
            execution_args["translation_context_mode"],
            plan.get("inspection"),
            requested_release_id=request.context_release_id,
            stale_choice=request.stale_choice,
            stale_acknowledgement=request.stale_acknowledgement,
        )
    if not isinstance(resolution, TranslationContextModeResolution):
        context_readiness = await readiness_service.inspect(
            request.project_id,
            execution_args["translation_context_mode"],
            plan.get("inspection"),
            requested_release_id=request.context_release_id,
        )
        resolution = TranslationContextModeResolution(
            execution_args["translation_context_mode"],
            execution_args["translation_context_mode"],
            context_readiness,
        )
    return resolution, resolution.readiness or await readiness_service.inspect(
        request.project_id,
        execution_args["translation_context_mode"],
        plan.get("inspection"),
        requested_release_id=request.context_release_id,
    )


def _game_plan_support(request, plan):
    from scripts.core.services.game_support_service import get_game_support, inspect_game_support
    inspection = plan.get("inspection") or {}
    game_id = inspection.get("game_id")
    support = get_game_support(game_id) if game_id else {}
    if request.custom_lang_config and (request.workflow == "incremental" or support.get("shell_languages_supported") is False):
        raise AgentTranslationPlanError(400, "unsupported_shell_language", "This game/workflow does not support Paradox shell-language configuration.")
    if request.workflow == "incremental" and request.use_resume:
        raise AgentTranslationPlanError(409, "incremental_resume_unsupported", "Create a fresh incremental plan; task-owned checkpoint resume is unavailable.")
    if game_id and support.get("output_kind") in {"independent_translation_mod", "csv_files"} and inspection.get("source_path"):
        support = inspect_game_support(game_id, inspection["source_path"], inspection.get("source_language", "en"))
        if not request.dry_run and (support["has_blocking_diagnostics"] or not support["recognized_resource_count"]):
            raise AgentTranslationPlanError(409, "game_resources_blocked", "Resolve blocking game resource diagnostics before translation.", {"game_support": support})
    return support


async def build_agent_translation_plan(
    request: AgentJobPlanRequest,
    *,
    api_providers: dict[str, dict[str, Any]],
    key_resolver: Callable[[str, str], str | None],
    plan_factory: Callable[..., Awaitable[dict[str, Any]]],
    readiness_service: Any,
    registry: Any,
    local_provider_ids: set[str],
) -> AgentPlanResponse:
    provider = api_providers.get(request.api_provider)
    if provider is None:
        raise AgentTranslationPlanError(400, "invalid_provider", "Unknown API provider")
    env_name = provider.get("api_key_env")
    if env_name and not key_resolver(request.api_provider, env_name):
        raise AgentTranslationPlanError(
            409,
            "provider_setup_required",
            (
                f"{provider.get('name') or request.api_provider} requires an API key. "
                "Configure it in Remis Settings > API Settings. If the user does not "
                "know what an API key is, explain it before continuing."
            ),
        )
    try:
        plan = await plan_factory(
            project_id=request.project_id,
            target_lang_codes=[
                item.value if hasattr(item, "value") else str(item)
                for item in request.target_lang_codes
            ],
            api_provider=request.api_provider,
            model=request.model,
            batch_size_limit=request.batch_size_limit,
            concurrency_limit=request.concurrency_limit,
            rpm_limit=request.rpm_limit,
            use_resume=request.use_resume,
            use_main_glossary=request.use_main_glossary,
            translation_context_mode=request.translation_context_mode,
            context_release_id=request.context_release_id,
            stale_choice=request.stale_choice,
            stale_acknowledgement=request.stale_acknowledgement,
            embedded_workshop_enabled=request.embedded_workshop_enabled,
            custom_lang_config=request.custom_lang_config,
        )
    except ValueError as exc:
        message = str(exc)
        code = "project_not_found" if "Project not found" in message else "invalid_request"
        raise AgentTranslationPlanError(
            404 if code == "project_not_found" else 400,
            code,
            message,
        ) from exc

    game_support = _game_plan_support(request, plan)
    execution_args = {**plan["execution_args"], "workflow": request.workflow}
    execution_args.setdefault("translation_context_mode", request.translation_context_mode)
    context_resolution, context_readiness = await _resolve_agent_context(
        request, execution_args, plan, readiness_service,
    )
    if context_resolution.requires_user_choice:
        raise AgentTranslationPlanError(
            409,
            "context_release_stale_choice_required",
            context_resolution.user_message or "Choose how to handle the stale archive.",
            {"context_readiness": context_readiness, "warning": context_resolution.warning},
        )
    execution_args["translation_context_mode"] = context_resolution.effective_mode
    execution_args["context_release_id"] = request.context_release_id
    execution_args["stale_choice"] = request.stale_choice
    execution_args["stale_acknowledgement"] = request.stale_acknowledgement
    stale_acknowledged = (
        context_readiness.get("archive", {}).get("readiness", {}).get("reason_code")
        == "context_release_stale"
        and request.stale_acknowledgement is not None
    )
    if not request.dry_run and not context_readiness["can_start"] and not stale_acknowledged and context_resolution.effective_mode == "archive":
        raise AgentTranslationPlanError(
            409,
            "project_context_not_ready",
            "The requested translation context is not ready for translation.",
            {"context_readiness": context_readiness},
        )

    summary = (
        "Read-only readiness check. No model call or localization output will be written."
        if request.dry_run
        else "Start the existing Remis translation workflow after explicit approval."
    )
    if context_readiness["status"] == "attention_required":
        summary += " Context readiness contains review warnings."
    record = registry.create_plan(
        project_id=request.project_id,
        execution_args=execution_args,
        dry_run=request.dry_run,
        summary=summary,
    )
    local_provider = request.api_provider in local_provider_ids
    return AgentPlanResponse(
        plan_id=record["plan_id"],
        status="ready" if request.dry_run else "awaiting_approval",
        project_id=request.project_id,
        dry_run=request.dry_run,
        requires_approval=not request.dry_run,
        risk={
            "writes_output": not request.dry_run,
            "may_use_paid_api": not request.dry_run and not local_provider,
            "overwrites_existing_output": False,
            "exports_to_game_directory": False,
            "context_readiness_attention": context_readiness["status"] != "ready",
        },
        summary=summary,
        allowed_actions=["start_dry_run"] if request.dry_run else ["approve_start"],
        context_readiness=context_readiness,
        translation={**language_plan_details(execution_args), "workflow": request.workflow},
        game_support=game_support,
        expires_at=record["expires_at"],
    )
