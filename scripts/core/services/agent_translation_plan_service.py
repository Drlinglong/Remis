"""Focused orchestration for Agent-owned initial translation plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from scripts.schemas.agent import AgentJobPlanRequest, AgentPlanResponse


@dataclass(frozen=True)
class AgentTranslationPlanError(RuntimeError):
    status_code: int
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)


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
            embedded_workshop_enabled=request.embedded_workshop_enabled,
        )
    except ValueError as exc:
        message = str(exc)
        code = "project_not_found" if "Project not found" in message else "invalid_request"
        raise AgentTranslationPlanError(
            404 if code == "project_not_found" else 400,
            code,
            message,
        ) from exc

    execution_args = plan["execution_args"]
    execution_args.setdefault("translation_context_mode", request.translation_context_mode)
    context_readiness = await readiness_service.inspect(
        request.project_id,
        execution_args["translation_context_mode"],
        plan.get("inspection"),
    )
    if not request.dry_run and not context_readiness["can_start"]:
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
        expires_at=record["expires_at"],
    )
