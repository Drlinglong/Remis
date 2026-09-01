"""Agent construction and bounded execution for archive research.

The backend facade owns request binding, compilation, and partial-artifact
policy.  This module owns the optional PydanticAI Harness integration: the
read-only tool surface, output/context capabilities, named child delegates,
and cancellation-aware lead execution.
"""

from __future__ import annotations

import asyncio
import contextlib
from copy import deepcopy
from typing import Any, Mapping

from pydantic_ai import RunContext

from scripts.core.services.context_research_corpus_tools import (
    BoundCorpusTools,
    CorpusToolLimits,
)
from scripts.core.services.context_research_read_metrics import CorpusReadMeter
from scripts.core.services.context_research_prompts import child_instructions, lead_instructions
from scripts.core.services.context_research_shard_memo import ShardMemo

try:
    from pydantic_ai_harness.planning import Planning
    from pydantic_ai_harness.subagents import SubAgent, SubAgents
    from pydantic_ai_harness.tool_output_limits import (
        Band,
        ToolOutputLimits as HarnessToolOutputLimits,
        Truncate,
    )
    from pydantic_ai_harness.compaction import ClearToolResults, WarnNearLimits

    HARNESS_AVAILABLE = True
    HARNESS_COMPATIBILITY_NOTE = "Harness capabilities loaded."
except ImportError:  # pragma: no cover
    Planning = SubAgent = SubAgents = Band = HarnessToolOutputLimits = Truncate = None
    ClearToolResults = WarnNearLimits = None
    HARNESS_AVAILABLE = False
    HARNESS_COMPATIBILITY_NOTE = (
        "Harness optional capabilities are unavailable because the installed "
        "PydanticAI/Harness versions are incompatible."
    )


ROLE_DESCRIPTIONS = {
    "cartographer": (
        "produce an evidence-backed entity register for named people, places, factions, "
        "polities, technologies, concepts, items, aliases, and recurring names"
    ),
    "event_investigator": "trace concrete events, sequence, causes, and consequences",
    "archive_lore": "inspect historical, cultural, and lore references without overclaiming",
    "evidence_auditor": (
        "check every claim against source_item_id evidence, audit every local unit for "
        "unaccounted sibling entries, and flag genuine coverage gaps"
    ),
}

SUBAGENT_REQUEST_LIMIT = 6
SUBAGENT_TOOL_CALL_LIMIT = 12
SUBAGENT_MAX_OUTPUT_TOKENS = 8000
SUBAGENT_OUTPUT_TOKEN_LIMIT = 24000
SUBAGENT_TIMEOUT_SECONDS = 180
LEAD_REQUEST_LIMIT = 20
LEAD_TOOL_CALL_LIMIT = 48
LEAD_MAX_OUTPUT_TOKENS = 16000
LEAD_OUTPUT_TOKEN_LIMIT = 32000


def merge_model_settings(
    default_max_tokens: int,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge role-local model settings without sharing mutable provider config."""

    merged: dict[str, Any] = {"max_tokens": default_max_tokens}
    if not overrides:
        return merged
    for key, value in overrides.items():
        if key == "extra_body" and value is not None:
            if not isinstance(value, Mapping):
                raise TypeError("model_settings.extra_body must be a mapping")
            merged[key] = deepcopy(dict(value))
        else:
            merged[key] = deepcopy(value)
    return merged


def usage_limits(requests: int, tool_calls: int, output_tokens: int) -> Any:
    """Create the provider-independent PydanticAI usage guard."""

    from pydantic_ai import UsageLimits

    return UsageLimits(
        request_limit=requests,
        tool_calls_limit=tool_calls,
        output_tokens_limit=output_tokens,
    )


def capabilities(limits: CorpusToolLimits) -> list[Any]:
    """Build bounded output and context capabilities for a corpus agent."""

    result: list[Any] = []
    if HarnessToolOutputLimits is not None:
        result.append(HarnessToolOutputLimits(
            bands=[Band(
                over=limits.max_total_chars,
                action=Truncate(max_chars=limits.max_total_chars),
            )],
            over_tokens=False,
        ))
    if ClearToolResults is not None:
        result.append(ClearToolResults(max_tokens=100_000, keep_pairs=3))
    if WarnNearLimits is not None:
        result.append(WarnNearLimits(max_context_fraction=0.9))
    return result


def _meter_for_deps(deps: Any) -> CorpusReadMeter | None:
    meter = getattr(deps, "_corpus_read_meter", None)
    if meter is not None:
        return meter
    bound = getattr(deps, "_bound", None)
    return getattr(bound, "_corpus_read_meter", None)


def _canonical_source_resolver(deps: Any) -> Any:
    registry = getattr(deps, "id_registry", None)
    if registry is None:
        registry = getattr(getattr(deps, "_bound", None), "id_registry", None)
    if registry is None:
        return None
    return lambda value: registry.source_by_alias.get(value, value)


async def _call_corpus_tool(
    ctx: RunContext[BoundCorpusTools],
    actor_role: str,
    tool: str,
    operation: Any,
) -> dict[str, Any]:
    meter = _meter_for_deps(ctx.deps)
    try:
        result = operation()
    except BaseException as error:
        if meter is not None and tool in {"read_units", "search_units", "read_investigation_shards", "read_corpus", "search_corpus"}:
            meter.record_failure(tool, actor_role=actor_role, error=error)
        raise
    if meter is not None and tool in {"read_units", "search_units", "read_investigation_shards", "read_corpus", "search_corpus"}:
        try:
            meter.observe(
                tool,
                result,
                actor_role=actor_role,
                source_id_resolver=_canonical_source_resolver(ctx.deps),
            )
        except BaseException as error:
            meter.record_failure(tool, actor_role=actor_role, error=error)
            raise
    return result


def register_corpus_tools(agent: Any, *, actor_role: str = "lead") -> None:
    """Register only the request-bound, read-only corpus functions."""

    @agent.tool
    async def list_units(
        ctx: RunContext[BoundCorpusTools], offset: int = 0, path: str | None = None,
    ) -> dict[str, Any]:
        return ctx.deps.list_local_units(offset=offset, path=path, _model_facing=True)

    @agent.tool
    async def search_units(ctx: RunContext[BoundCorpusTools], query: str) -> dict[str, Any]:
        return await _call_corpus_tool(
            ctx, actor_role, "search_units",
            lambda: ctx.deps.search_local_units(query, _model_facing=True),
        )

    @agent.tool
    async def read_units(
        ctx: RunContext[BoundCorpusTools], local_unit_ids: list[str],
    ) -> dict[str, Any]:
        return await _call_corpus_tool(
            ctx, actor_role, "read_units",
            lambda: ctx.deps.read_local_units(local_unit_ids, _model_facing=True),
        )

    @agent.tool
    async def corpus_manifest(ctx: RunContext[BoundCorpusTools]) -> dict[str, Any]:
        return ctx.deps.corpus_manifest(_model_facing=True)

    @agent.tool
    async def list_investigation_shards(
        ctx: RunContext[BoundCorpusTools], offset: int = 0,
    ) -> dict[str, Any]:
        return ctx.deps.investigation_shards(offset=offset, _model_facing=True)

    @agent.tool
    async def read_investigation_shards(
        ctx: RunContext[BoundCorpusTools], shard_ids: list[str],
    ) -> dict[str, Any]:
        return await _call_corpus_tool(
            ctx, actor_role, "read_investigation_shards",
            lambda: ctx.deps.read_investigation_shards(shard_ids, _model_facing=True),
        )

    @agent.tool
    async def list_corpus(
        ctx: RunContext[BoundCorpusTools], offset: int = 0, path: str | None = None,
    ) -> dict[str, Any]:
        return ctx.deps.list_source_items(offset=offset, path=path, _model_facing=True)

    @agent.tool
    async def search_corpus(ctx: RunContext[BoundCorpusTools], query: str) -> dict[str, Any]:
        return await _call_corpus_tool(
            ctx, actor_role, "search_corpus",
            lambda: ctx.deps.search_source_items(query, _model_facing=True),
        )

    @agent.tool
    async def read_corpus(
        ctx: RunContext[BoundCorpusTools], source_item_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await _call_corpus_tool(
            ctx, actor_role, "read_corpus",
            lambda: ctx.deps.read_source_items(source_item_ids, _model_facing=True),
        )


def build_child_delegates(
    *,
    agent_type: Any,
    subagent_model: Any,
    tool_limits: CorpusToolLimits,
    delegation_tracker: Any | None,
    role_max_calls: int,
    subagent_model_settings: Mapping[str, Any] | None = None,
) -> list[Any]:
    """Build four named, bounded child delegates for the lead capability."""

    children: list[Any] = []
    for role, description in ROLE_DESCRIPTIONS.items():
        child = agent_type(
            subagent_model,
            name=f"archive_{role}",
            deps_type=BoundCorpusTools,
            output_type=ShardMemo,
            instructions=child_instructions(role, description),
            retries={"tools": 1, "output": 2},
            model_settings=merge_model_settings(
                SUBAGENT_MAX_OUTPUT_TOKENS,
                subagent_model_settings,
            ),
            capabilities=capabilities(tool_limits),
        )
        register_corpus_tools(child, actor_role=role)
        child_for_delegation = (
            delegation_tracker.wrap(child, role)
            if delegation_tracker is not None else child
        )
        if delegation_tracker is not None:
            delegation_tracker.mark_bound()
        children.append(SubAgent(
            agent=child_for_delegation,
            name=role,
            description=description,
            max_calls=role_max_calls,
            timeout_seconds=SUBAGENT_TIMEOUT_SECONDS,
            usage_limits=usage_limits(
                SUBAGENT_REQUEST_LIMIT,
                SUBAGENT_TOOL_CALL_LIMIT,
                SUBAGENT_OUTPUT_TOKEN_LIMIT,
            ),
            contain_errors=True,
        ))
    return children


def build_lead_agent(
    *,
    model: Any,
    subagent_model: Any,
    tool_limits: CorpusToolLimits,
    output_type: Any,
    delegation_tracker: Any | None,
    role_max_calls: int,
    lead_model_settings: Mapping[str, Any] | None = None,
    subagent_model_settings: Mapping[str, Any] | None = None,
) -> Any:
    """Construct a lead agent with planning, subagents, and bounded output."""

    if not HARNESS_AVAILABLE:
        raise RuntimeError(HARNESS_COMPATIBILITY_NOTE)
    from pydantic_ai import Agent

    children = build_child_delegates(
        agent_type=Agent,
        subagent_model=subagent_model,
        tool_limits=tool_limits,
        delegation_tracker=delegation_tracker,
        role_max_calls=role_max_calls,
        subagent_model_settings=subagent_model_settings,
    )
    agent_capabilities: list[Any] = [
        Planning(
            guidance=(
                "Create a short plan first. Delegate bounded tasks, ensuring "
                "each required role receives at least one task. After inspecting a result, "
                "you may revisit the same role when a shard needs clarification or overlap."
            ),
            enable_subtasks=True,
            inject=True,
        ),
        SubAgents(
            agents=children,
            inherit_tools=False,
            forward_usage=False,
            tool_retries=1,
            contain_errors=True,
        ),
    ]
    agent_capabilities.extend(capabilities(tool_limits))
    agent = Agent(
        model,
        name="archive_research_lead",
        deps_type=BoundCorpusTools,
        output_type=output_type,
        instructions=lead_instructions(),
        model_settings=merge_model_settings(
            LEAD_MAX_OUTPUT_TOKENS,
            lead_model_settings,
        ),
        capabilities=agent_capabilities,
    )
    register_corpus_tools(agent)
    return agent


async def run_lead(
    agent: Any,
    prompt: str,
    bound_tools: BoundCorpusTools,
    *,
    message_history: Any = None,
) -> Any:
    """Run one bounded lead pass; retry/completion policy stays in the facade."""

    kwargs: dict[str, Any] = {
        "deps": bound_tools,
        "usage_limits": usage_limits(
            LEAD_REQUEST_LIMIT,
            LEAD_TOOL_CALL_LIMIT,
            LEAD_OUTPUT_TOKEN_LIMIT,
        ),
    }
    if message_history is not None:
        kwargs["message_history"] = message_history
    return await agent.run(prompt, **kwargs)


async def await_with_cancellation(task: asyncio.Task[Any], context: Any) -> Any:
    """Race a model task with the owner cancellation signal."""

    async def watch() -> None:
        while not context.cancellation.is_cancelled():
            await asyncio.sleep(0.05)

    watcher = asyncio.create_task(watch())
    done, _ = await asyncio.wait({task, watcher}, return_when=asyncio.FIRST_COMPLETED)
    if watcher in done and context.cancellation.is_cancelled():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise asyncio.CancelledError("archive research cancelled")
    watcher.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await watcher
    return task.result()


__all__ = [
    "HARNESS_AVAILABLE",
    "HARNESS_COMPATIBILITY_NOTE",
    "LEAD_REQUEST_LIMIT",
    "LEAD_TOOL_CALL_LIMIT",
    "LEAD_MAX_OUTPUT_TOKENS",
    "LEAD_OUTPUT_TOKEN_LIMIT",
    "ROLE_DESCRIPTIONS",
    "SUBAGENT_MAX_OUTPUT_TOKENS",
    "SUBAGENT_OUTPUT_TOKEN_LIMIT",
    "SUBAGENT_REQUEST_LIMIT",
    "SUBAGENT_TIMEOUT_SECONDS",
    "SUBAGENT_TOOL_CALL_LIMIT",
    "await_with_cancellation",
    "build_lead_agent",
    "capabilities",
    "merge_model_settings",
    "register_corpus_tools",
    "run_lead",
    "usage_limits",
]
