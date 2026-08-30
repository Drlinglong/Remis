"""PydanticAI implementation of the LM Studio Help Copilot."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from scripts.app_settings import API_PROVIDERS, config_manager
from scripts.core.copilot.help_pack import AGENT_OPS_SUMMARY, HELP_SKILLS, read_help_skills
from scripts.core.copilot.settings import pydantic_reasoning_settings
from scripts.core.services.provider_runtime import ProviderRuntimeSnapshot

HelpSkillId = Enum("HelpSkillId", {skill_id.upper(): skill_id for skill_id in HELP_SKILLS}, type=str)


class HelpActionChoice(BaseModel):
    action: str
    args: dict[str, Any] = Field(default_factory=dict)


class HelpAnswer(BaseModel):
    reply: str
    suggested_actions: list[HelpActionChoice] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


@dataclass
class HelpDeps:
    loaded_excerpts: list[dict[str, str]] = field(default_factory=list)
    selected_skill_ids: list[str] = field(default_factory=list)
    no_match_reason: str | None = None


def _lm_studio_config(model_name: str | None) -> tuple[str, str]:
    config = dict(API_PROVIDERS.get("lm_studio", {}))
    overrides = config_manager.get_value("provider_config", {}).get("lm_studio", {}) or {}
    base_url = str(overrides.get("api_url") or config.get("base_url") or "http://localhost:1234/v1")
    selected_model = model_name or overrides.get("selected_model") or config.get("default_model") or "local-model"
    return base_url, str(selected_model)


def build_help_agent(
    model_name: str | None = None,
    *,
    reasoning_override: dict[str, Any] | None = None,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> Agent[HelpDeps, HelpAnswer]:
    if provider_runtime is None:
        base_url, selected_model = _lm_studio_config(model_name)
        provider_id = "lm_studio"
        provider_config = None
        api_key = "local-no-key-required"
    else:
        base_url = str(provider_runtime.config.get("base_url") or "http://localhost:1234/v1")
        selected_model = provider_runtime.model_id or model_name or "local-model"
        provider_id = provider_runtime.adapter_id
        provider_config = provider_runtime.config
        api_key = provider_runtime.api_key or "local-no-key-required"
    model = OpenAIResponsesModel(
        selected_model,
        provider=OpenAIProvider(base_url=base_url, api_key=api_key),
    )
    catalog = "\n".join(
        f"- {skill_id}: {meta['title']}，{meta['description']}"
        for skill_id, meta in HELP_SKILLS.items()
    )
    agent = Agent(
        model,
        deps_type=HelpDeps,
        output_type=HelpAnswer,
        instructions=(
            "你是 Remis 产品帮助助手。回答前必须按需调用 read_help_skill；确实无覆盖时调用 report_no_help_skill。"
            "最多读取三个技能。不要猜测文档未覆盖的产品细节。只建议允许的 Remis action ID。\n\n"
            f"{AGENT_OPS_SUMMARY}\n\n可用帮助技能：\n{catalog}"
        ),
        model_settings=OpenAIResponsesModelSettings(
            temperature=0.1,
            max_tokens=1200,
            timeout=90,
            parallel_tool_calls=True,
            **pydantic_reasoning_settings(
                provider=provider_id,
                model=selected_model,
                enabled=bool((reasoning_override or {}).get("reasoning_builtin_enabled")),
                preset=str((reasoning_override or {}).get("reasoning_preset") or "medium"),
                provider_config=provider_config,
            ),
        ),
        retries=1,
        tool_timeout=10,
    )

    @agent.tool
    async def read_help_skill(ctx: RunContext[HelpDeps], skill_id: HelpSkillId) -> dict[str, Any]:
        """Read one allowlisted Remis help skill bundled with the application."""
        value = str(skill_id.value)
        if value in ctx.deps.selected_skill_ids:
            return {"skill_id": value, "already_loaded": True}
        if len(ctx.deps.selected_skill_ids) >= 3:
            return {"skill_id": value, "error": "maximum_help_skills_reached"}
        excerpts = read_help_skills([value])
        ctx.deps.selected_skill_ids.append(value)
        ctx.deps.loaded_excerpts.extend(excerpts)
        return {"skill_id": value, "documents": excerpts}

    @agent.tool
    async def report_no_help_skill(ctx: RunContext[HelpDeps], reason: str) -> dict[str, Any]:
        """Report that no packaged help skill can ground this answer."""
        ctx.deps.no_match_reason = reason[:500]
        return {"recorded": True, "reason": ctx.deps.no_match_reason}

    @agent.output_validator
    async def validate_help_answer(ctx: RunContext[HelpDeps], output: HelpAnswer) -> HelpAnswer:
        if not ctx.deps.loaded_excerpts and not ctx.deps.no_match_reason:
            raise ModelRetry("Read a help skill or call report_no_help_skill before answering")
        if not ctx.deps.loaded_excerpts:
            output.confidence = "low"
        return output

    return agent


def run_pydantic_help_agent(
    history: list[dict[str, str]],
    *,
    model_name: str | None = None,
    page_context: dict[str, Any] | None = None,
    reasoning_override: dict[str, Any] | None = None,
    provider_runtime: ProviderRuntimeSnapshot | None = None,
) -> dict[str, Any]:
    deps = HelpDeps()
    agent = build_help_agent(
        model_name,
        reasoning_override=reasoning_override,
        provider_runtime=provider_runtime,
    )
    result = agent.run_sync(
        "结合以下对话和只读页面上下文回答最后一个用户问题。不得声称已执行页面操作。\n"
        + json.dumps({"history": history[-12:], "page_context": page_context or {}}, ensure_ascii=False),
        deps=deps,
        usage_limits=UsageLimits(request_limit=5, tool_calls_limit=4, output_tokens_limit=5000),
    )
    return {
        "answer": result.output,
        "selected_skill_ids": deps.selected_skill_ids,
        "excerpts": deps.loaded_excerpts,
        "no_match_reason": deps.no_match_reason,
        "usage": asdict(result.usage if not callable(result.usage) else result.usage()),
    }
