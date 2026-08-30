"""PydanticAI Help Copilot for OpenAI-compatible Remis providers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from scripts.core.copilot.help_pack import AGENT_OPS_SUMMARY, HELP_SKILLS, read_help_skills
from scripts.core.copilot.help_agent_models import build_help_model, supports_pydantic_help_agent
from scripts.core.copilot.actions import LocalizationWorkflowArgs
from scripts.core.copilot.task_status import get_copilot_task_status

HelpSkillId = Enum("HelpSkillId", {skill_id.upper(): skill_id for skill_id in HELP_SKILLS}, type=str)

_TASK_ID_PATTERN = re.compile(
    r"\b(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|job_[a-z0-9_-]+)\b",
    re.IGNORECASE,
)
_TASK_STATUS_INTENT_PATTERN = re.compile(
    r"(?:翻译|任务|作业|task|job).{0,16}(?:进度|状态|完成|失败|结果)"
    r"|(?:进度|状态).{0,16}(?:如何|怎样|怎么样|多少|查询|查看)"
    r"|(?:task|job)\s+(?:status|progress|result)"
    r"|(?:status|progress)\s+(?:of|for)\s+(?:the\s+)?(?:task|job)",
    re.IGNORECASE,
)


class HelpActionChoice(BaseModel):
    action: Literal[
        "open_api_settings", "open_log_folder", "open_github_issues", "open_github_issue_132",
        "open_project_management", "open_create_project", "open_initial_translation",
        "open_proofreading", "open_agent_workshop", "open_glossary_manager",
        "open_provider_docs", "open_deploy_dialog",
    ]
    args: dict[str, Any] = Field(default_factory=dict)


class WorkflowActionChoice(BaseModel):
    action: Literal["start_localization_workflow"]
    args: LocalizationWorkflowArgs


SuggestedHelpAction = Annotated[
    HelpActionChoice | WorkflowActionChoice,
    Field(discriminator="action"),
]


class HelpAnswer(BaseModel):
    reply: str
    suggested_actions: list[SuggestedHelpAction] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"


@dataclass
class HelpDeps:
    loaded_excerpts: list[dict[str, str]] = field(default_factory=list)
    selected_skill_ids: list[str] = field(default_factory=list)
    no_match_reason: str | None = None
    workflow_entities: dict[str, Any] = field(default_factory=dict)
    inspected_workflow_entities: bool = False
    required_task_ids: list[str] = field(default_factory=list)
    task_status_results: dict[str, dict[str, Any]] = field(default_factory=dict)


def task_ids_requiring_status_lookup(history: list[dict[str, str]]) -> list[str]:
    """Find the most recent task ID when the latest user message asks for task state."""
    latest_user = next(
        (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "user"),
        "",
    )
    if not _TASK_STATUS_INTENT_PATTERN.search(latest_user):
        return []
    latest_ids = _TASK_ID_PATTERN.findall(latest_user)
    if latest_ids:
        return [latest_ids[-1]]
    for item in reversed(history):
        identifiers = _TASK_ID_PATTERN.findall(str(item.get("content") or ""))
        if identifiers:
            return [identifiers[-1]]
    return []


def build_help_agent(
    provider: str,
    model_name: str | None = None,
    *,
    reasoning_override: dict[str, Any] | None = None,
) -> Agent[HelpDeps, HelpAnswer]:
    model, model_settings, _ = build_help_model(provider, model_name, reasoning_override)
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
            "最多读取三个技能。用户要求 Agent 规划或提到已有项目、Provider、模型时，必须调用 "
            "inspect_workflow_entities，再从结果中选择规范实体。不要猜测文档未覆盖的产品细节。"
            "用户询问某个翻译任务的进度、状态或结果时，必须使用对话中的 task ID 调用 "
            "get_task_status；只能依据该工具的权威结果回答，不得从聊天中推断任务终态。"
            "只建议允许的 Remis action ID。\n\n"
            f"{AGENT_OPS_SUMMARY}\n\n可用帮助技能：\n{catalog}"
        ),
        model_settings=model_settings,
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

    @agent.tool
    async def inspect_workflow_entities(ctx: RunContext[HelpDeps]) -> dict[str, Any]:
        """List safe Remis projects, providers, and configured models without paths or secrets."""
        ctx.deps.inspected_workflow_entities = True
        return ctx.deps.workflow_entities

    @agent.tool
    async def get_task_status(ctx: RunContext[HelpDeps], task_id: str) -> dict[str, Any]:
        """Read a task's authoritative persisted status, validation, and output summary."""
        result = await get_copilot_task_status(task_id)
        ctx.deps.task_status_results[str(task_id)] = result
        return result

    @agent.output_validator
    async def validate_help_answer(ctx: RunContext[HelpDeps], output: HelpAnswer) -> HelpAnswer:
        if not ctx.deps.loaded_excerpts and not ctx.deps.no_match_reason:
            raise ModelRetry("Read a help skill or call report_no_help_skill before answering")
        if not ctx.deps.loaded_excerpts:
            output.confidence = "low"
        missing_task_ids = [
            task_id for task_id in ctx.deps.required_task_ids
            if task_id not in ctx.deps.task_status_results
        ]
        if missing_task_ids:
            raise ModelRetry(
                f"Call get_task_status for the required task ID before answering: {missing_task_ids[0]}"
            )
        wants_workflow = any(item.action == "start_localization_workflow" for item in output.suggested_actions)
        if wants_workflow and not ctx.deps.inspected_workflow_entities:
            raise ModelRetry("Call inspect_workflow_entities before proposing a localization workflow")
        if wants_workflow:
            from scripts.core.copilot.actions import filter_suggested_actions

            cleaned = filter_suggested_actions(
                [item.model_dump() for item in output.suggested_actions],
                workflow_entity_catalog=ctx.deps.workflow_entities,
            )
            workflow = next(
                (item for item in cleaned if item["action"] == "start_localization_workflow"),
                None,
            )
            if workflow is None:
                raise ModelRetry(
                    "Return complete typed workflow args from the inspected catalogue: project_mode, "
                    "project_id/project_name, target_languages, api_provider, and model"
                )
            output.suggested_actions = [
                item for item in output.suggested_actions if item.action != "start_localization_workflow"
            ] + [WorkflowActionChoice(action="start_localization_workflow", args=workflow["args"])]
        return output

    return agent


def run_pydantic_help_agent(
    history: list[dict[str, str]],
    *,
    provider: str = "lm_studio",
    model_name: str | None = None,
    page_context: dict[str, Any] | None = None,
    reasoning_override: dict[str, Any] | None = None,
    workflow_entity_catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deps = HelpDeps(
        workflow_entities=workflow_entity_catalog or {},
        required_task_ids=task_ids_requiring_status_lookup(history),
    )
    agent = build_help_agent(
        provider,
        model_name,
        reasoning_override=reasoning_override,
    )
    result = agent.run_sync(
        "结合以下对话和只读页面上下文回答最后一个用户问题。不得声称已执行页面操作。\n"
        + json.dumps({"history": history[-12:], "page_context": page_context or {}}, ensure_ascii=False),
        deps=deps,
        usage_limits=UsageLimits(request_limit=5, tool_calls_limit=5, output_tokens_limit=5000),
    )
    return {
        "answer": result.output,
        "selected_skill_ids": deps.selected_skill_ids,
        "workflow_entities_inspected": deps.inspected_workflow_entities,
        "task_status_lookups": deps.task_status_results,
        "excerpts": deps.loaded_excerpts,
        "no_match_reason": deps.no_match_reason,
        "usage": asdict(result.usage if not callable(result.usage) else result.usage()),
    }
