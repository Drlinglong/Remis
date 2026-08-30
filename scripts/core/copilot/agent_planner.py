"""PydanticAI workflow planner with Remis-owned read-only dependencies."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from scripts.core.copilot.read_tools import execute_workflow_read_tool
from scripts.core.copilot.settings import pydantic_reasoning_settings
from scripts.core.copilot.runtime import resolve_provider_runtime_snapshot
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot


class TranslationRecommendation(BaseModel):
    summary: str
    api_provider: str
    model: str
    batch_size_limit: int = Field(ge=1, le=1000)
    concurrency_limit: int = Field(ge=1, le=100)
    rpm_limit: int = Field(ge=1, le=100000)
    use_resume: bool = True
    use_main_glossary: bool = True
    embedded_workshop_enabled: bool = True
    warnings: list[str] = Field(default_factory=list)


@dataclass
class PlannerDeps:
    project_id: str
    target_lang_codes: list[str]
    preferred_provider: str
    inspected_context: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


def _build_agent(
    *,
    provider: str,
    model_name: str | None,
    reasoning_enabled: bool,
    reasoning_preset: str,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> Agent[PlannerDeps, TranslationRecommendation]:
    runtime = provider_runtime or resolve_provider_runtime_snapshot(provider, model_name)
    provider_config = runtime.config
    base_url = str(provider_config.get("base_url") or "http://localhost:1234/v1")
    selected_model = runtime.model_id or model_name or "local-model"
    api_key = runtime.api_key or "local-no-key-required"
    responses_model = OpenAIResponsesModel(
        selected_model,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key or "missing-api-key"),
    )
    agent = Agent(
        responses_model,
        deps_type=PlannerDeps,
        output_type=TranslationRecommendation,
        instructions=(
            "你是 Remis 初次翻译工作流规划 Agent。必须先调用 inspect_translation_context。"
            "根据只读结果给出保守配置，不得发明未列出的模型。"
            "优先 preferred_provider，除非工具明确显示不可用。不要执行翻译。"
        ),
        model_settings=OpenAIResponsesModelSettings(
            temperature=0.0,
            max_tokens=1024,
            timeout=90,
            parallel_tool_calls=False,
            **pydantic_reasoning_settings(
                provider=runtime.adapter_id,
                model=selected_model,
                enabled=reasoning_enabled,
                preset=reasoning_preset,
                provider_config=provider_config,
            ),
        ),
        retries=1,
        tool_timeout=20,
    )

    @agent.tool
    async def inspect_translation_context(ctx: RunContext[PlannerDeps]) -> dict[str, Any]:
        """Read bounded project, file, provider/model, glossary, and checkpoint context."""
        result = await execute_workflow_read_tool(
            "inspect_translation_context",
            {},
            project_id=ctx.deps.project_id,
            target_lang_codes=ctx.deps.target_lang_codes,
            preferred_provider=ctx.deps.preferred_provider,
        )
        ctx.deps.inspected_context = result
        ctx.deps.tool_calls.append({"name": "inspect_translation_context", "arguments": {}})
        return result

    @agent.output_validator
    async def validate_recommendation(
        ctx: RunContext[PlannerDeps], output: TranslationRecommendation
    ) -> TranslationRecommendation:
        if not ctx.deps.inspected_context:
            raise ModelRetry("Call inspect_translation_context before submitting a plan")
        model_info = ctx.deps.inspected_context.get("models", {})
        allowed_models = set(model_info.get("models", []))
        if output.api_provider != model_info.get("provider") or output.model not in allowed_models:
            raise ModelRetry("Choose a provider and model verified by inspect_translation_context")
        return output

    return agent


async def recommend_initial_translation(
    *,
    project_id: str,
    target_lang_codes: list[str],
    preferred_provider: str,
    provider: str = "lm_studio",
    model: str | None = None,
    reasoning_enabled: bool = False,
    reasoning_preset: str = "medium",
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> dict[str, Any]:
    deps = PlannerDeps(
        project_id=project_id,
        target_lang_codes=target_lang_codes,
        preferred_provider=preferred_provider,
    )
    runtime = provider_runtime or resolve_provider_runtime_snapshot(provider, model)
    agent = _build_agent(
        provider=provider,
        model_name=runtime.model_id,
        reasoning_enabled=reasoning_enabled,
        reasoning_preset=reasoning_preset,
        provider_runtime=runtime,
    )
    result = await agent.run(
        f"为项目制定初次翻译建议。目标语言：{target_lang_codes}；preferred_provider：{preferred_provider}。",
        deps=deps,
        usage_limits=UsageLimits(request_limit=4, tool_calls_limit=2, output_tokens_limit=3600),
    )
    return {
        "recommendation": result.output.model_dump(),
        "tool_calls": deps.tool_calls,
        "tool_results": ([{"tool": "inspect_translation_context", "result": deps.inspected_context}] if deps.inspected_context else []),
        "read_only": True,
        "usage": asdict(result.usage if not callable(result.usage) else result.usage()),
    }
