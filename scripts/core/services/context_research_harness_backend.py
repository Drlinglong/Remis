"""Developer-only PydanticAI Harness backend for local archive research.

The shared research contract remains the only DTO boundary. This adapter is
not registered with a Remis workflow and has no publish, write, shell, web, or
filesystem capability. Host-side source, delegation, usage, and cancellation
limits remain authoritative when Harness capabilities are installed.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import (
    ContextResearchDraftCompiler,
    ContextResearchFindings,
)
from scripts.core.services.context_research_corpus_tools import (
    BoundCorpusTools,
    CorpusToolLimits,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_harness_run import (
    ContextResearchRunCoordinator,
    DelegationTracker,
    REQUIRED_ROLE_NAMES,
)
from scripts.core.services.context_research_prompts import completion_prompt, initial_prompt
from scripts.core.services.context_research_harness_agent import (
    HARNESS_AVAILABLE,
    HARNESS_COMPATIBILITY_NOTE,
    LEAD_MAX_OUTPUT_TOKENS,
    LEAD_OUTPUT_TOKEN_LIMIT,
    LEAD_REQUEST_LIMIT,
    LEAD_TOOL_CALL_LIMIT,
    ADJUDICATION_MAX_OUTPUT_TOKENS,
    ADJUDICATION_OUTPUT_TOKEN_LIMIT,
    ADJUDICATION_REQUEST_LIMIT,
    ROLE_DESCRIPTIONS,
    SUBAGENT_MAX_OUTPUT_TOKENS,
    SUBAGENT_OUTPUT_TOKEN_LIMIT,
    SUBAGENT_REQUEST_LIMIT,
    SUBAGENT_TIMEOUT_SECONDS,
    SUBAGENT_TOOL_CALL_LIMIT,
    await_with_cancellation,
    build_lead_agent,
    build_adjudication_agent,
    merge_model_settings,
    run_lead,
    run_adjudication,
)
from scripts.core.services.context_research_trace_ledger import ContextResearchTraceCollector
from scripts.core.services.context_research_read_metrics import CorpusReadMeter
from scripts.core.services.context_research_lead_decisions import LeadResearchResult
from scripts.core.services.context_research_shard_memo import ShardMemoCollector

if TYPE_CHECKING:
    from scripts.core.services.context_research_contract import (
        AgentExecutionContext,
        ContextAnalysisRequest,
        ContextResearchBackend,
        ContextResearchDraft,
    )

try:
    from scripts.core.services.context_research_contract import ContextResearchBackend as _ContractBackend
except ImportError:  # pragma: no cover
    _ContractBackend = object

MAX_ROLE_CALLS_PER_RUN = 3


def _model_label(model: Any) -> str:
    for name in ("model_name", "model_id", "name"):
        value = getattr(model, name, None)
        if isinstance(value, str) and value.strip():
            return value
    return type(model).__name__


def _materialize_request(request: Any, bound_tools: BoundCorpusTools) -> Any:
    """Give the compiler the same canonical snapshot used by ID-only tools."""

    if request.source_items:
        return request
    source_items = tuple(
        SourceItem(
            source_item_id=item.source_item_id,
            relative_path=item.relative_path or "unknown/source.txt",
            item_key=item.item_key or None,
            source_order=(
                item.source_order if item.source_order is not None else index
            ),
            duplicate_key_ordinal=int(
                (item.metadata or {}).get("duplicate_key_ordinal", 0) or 0
            ),
            source_text=item.source_text,
        )
        for index, item in enumerate(bound_tools.materialized_source_items)
    )
    return request.model_copy(update={"source_items": source_items})


class PydanticAIContextResearchBackend(_ContractBackend):
    """One real Harness lead with four named, bounded subagents."""

    developer_only = True
    supports_in_flight_resume = False

    def __init__(self, *, corpus_tools: ReadOnlyRemisCorpusTools, model: Any | None = None,
                 lead_model: Any | None = None,
                 subagent_model: Any | None = None,
                 lead_model_settings: Mapping[str, Any] | None = None,
                 subagent_model_settings: Mapping[str, Any] | None = None,
                 tool_limits: CorpusToolLimits | None = None,
                 compiler: ContextResearchDraftCompiler | None = None,
                 trace_output_path: str | Path | None = None,
                 max_repair_attempts: int = 2) -> None:
        required = ("list_source_items", "search_source_items", "read_source_items")
        if not all(callable(getattr(corpus_tools, name, None)) for name in required):
            raise TypeError("corpus_tools must expose the Remis read-only corpus surface")
        if model is None and lead_model is None:
            raise TypeError("model or lead_model must be supplied")
        self.corpus_tools = corpus_tools
        self.model = model
        self.lead_model = lead_model if lead_model is not None else model
        self.subagent_model = (
            subagent_model if subagent_model is not None else self.lead_model
        )
        self.lead_model_settings = merge_model_settings(
            LEAD_MAX_OUTPUT_TOKENS,
            lead_model_settings,
        )
        self.subagent_model_settings = merge_model_settings(
            SUBAGENT_MAX_OUTPUT_TOKENS,
            subagent_model_settings,
        )
        self.adjudication_model_settings = merge_model_settings(
            ADJUDICATION_MAX_OUTPUT_TOKENS,
            lead_model_settings,
        )
        self.tool_limits = tool_limits or getattr(corpus_tools, "limits", CorpusToolLimits())
        self.compiler = compiler or ContextResearchDraftCompiler()
        self.trace_output_path = Path(trace_output_path) if trace_output_path else None
        self.run_coordinator = ContextResearchRunCoordinator(
            self.compiler, max_repair_attempts=max_repair_attempts,
        )
        self.last_trace_snapshot: dict[str, Any] | None = None

    @staticmethod
    def _adaptive_role_budget(local_unit_count: int) -> int:
        """Scale revisits to corpus size while retaining a hard per-role cap."""

        if local_unit_count <= 12:
            return 1
        if local_unit_count <= 64:
            return 3
        return 8

    def build_agent(
        self,
        *,
        model: Any | None = None,
        output_type: Any = LeadResearchResult,
        delegation_tracker: DelegationTracker | None = None,
        role_max_calls: int = MAX_ROLE_CALLS_PER_RUN,
    ) -> Any:
        """Construct a lead Agent with Planning, SubAgents, and bounded output."""

        selected_model = self.lead_model if model is None else model
        return build_lead_agent(
            model=selected_model,
            subagent_model=self.subagent_model,
            tool_limits=self.tool_limits,
            output_type=output_type,
            delegation_tracker=delegation_tracker,
            role_max_calls=role_max_calls,
            lead_model_settings=self.lead_model_settings,
            subagent_model_settings=self.subagent_model_settings,
        )

    async def _run_lead(
        self,
        agent: Any,
        prompt: str,
        bound_tools: BoundCorpusTools,
        *,
        message_history: Any = None,
    ) -> Any:
        """Run one bounded lead pass; the caller owns retry/completion policy."""

        return await run_lead(
            agent,
            prompt,
            bound_tools,
            message_history=message_history,
        )

    def build_adjudication_agent(self) -> Any:
        """Build the no-tools one-request edge adjudicator."""

        return build_adjudication_agent(
            model=self.lead_model,
            model_settings=self.adjudication_model_settings,
        )

    async def _run_adjudication(self, agent: Any, prompt: str) -> Any:
        """Run only the bounded adjudication request."""

        return await run_adjudication(agent, prompt)

    def _build_adjudication_runner(self, execution_context: Any) -> Any:
        agent = None

        async def runner(prompt: str) -> Any:
            nonlocal agent
            if agent is None:
                agent = self.build_adjudication_agent()
            task = asyncio.create_task(self._run_adjudication(agent, prompt))
            return await await_with_cancellation(task, execution_context)

        runner.model_label = _model_label(getattr(self.lead_model, "model", self.lead_model))
        return runner

    async def _recover_partial_lead(
        self,
        agent: Any,
        bound_tools: BoundCorpusTools,
        tracker: DelegationTracker,
        request: "ContextAnalysisRequest",
        execution_context: "AgentExecutionContext",
        run_lead: Any,
        trace: ContextResearchTraceCollector,
    ) -> tuple[ContextResearchFindings, bool]:
        """Give missing roles one bounded completion pass after a lead failure."""

        findings = ContextResearchFindings()
        if not tracker.bound or not tracker.missing_roles:
            return findings, False
        missing_roles = tracker.missing_roles
        try:
            result = await run_lead(
                agent,
                completion_prompt(missing_roles),
                bound_tools,
            )
            _, legacy_findings = self.run_coordinator._record_lead(
                result, execution_context, trace, "completion", 1,
                _model_label(getattr(agent, "model", None)),
            )
            return legacy_findings, True
        except asyncio.CancelledError:
            raise
        except Exception as error:
            trace.record_error(error, stage="completion")
            execution_context.events.emit("research_completion_failed", {
                "read_only": True,
                "error_type": type(error).__name__,
                "partial_artifact_retained": True,
                "missing_roles": list(missing_roles),
            })
            return findings, True

    async def _retain_after_lead_failure(
        self,
        error: Exception,
        agent: Any,
        bound_tools: BoundCorpusTools,
        tracker: DelegationTracker,
        request: "ContextAnalysisRequest",
        execution_context: "AgentExecutionContext",
        run_lead: Any,
        trace: ContextResearchTraceCollector,
    ) -> "ContextResearchDraft":
        trace.record_error(error, stage="lead")
        execution_context.events.emit("research_failed", {
            "read_only": True,
            "error_type": type(error).__name__,
            "partial_artifact_retained": True,
        })
        findings, completion_attempted = await self._recover_partial_lead(
            agent, bound_tools, tracker, request, execution_context, run_lead, trace,
        )
        return self.run_coordinator.finalize_partial(
            findings=findings,
            tracker=tracker,
            request=request,
            completion_attempted=completion_attempted,
            trace=trace,
        )

    @staticmethod
    def _build_delegation_tracker(
        execution_context: "AgentExecutionContext",
        trace: ContextResearchTraceCollector,
        bound_tools: BoundCorpusTools,
    ) -> DelegationTracker:
        return DelegationTracker(
            execution_context.events,
            trace,
            memo_collector=ShardMemoCollector(
                bound_tools.investigation_manifest(), id_registry=bound_tools.id_registry,
            ),
            id_registry=bound_tools.id_registry,
        )

    def _retain_after_finalization_failure(
        self,
        error: Exception,
        findings: ContextResearchFindings,
        tracker: DelegationTracker,
        request: "ContextAnalysisRequest",
        trace: ContextResearchTraceCollector,
    ) -> "ContextResearchDraft":
        trace.record_error(error, stage="finalization")
        return self.run_coordinator.finalize_partial(
            findings=findings,
            tracker=tracker,
            request=request,
            completion_attempted=False,
            trace=trace,
        )

    async def analyze(
        self,
        request: "ContextAnalysisRequest",
        execution_context: "AgentExecutionContext",
    ) -> "ContextResearchDraft":
        """Run Harness against the immutable, request-bound source snapshot."""

        if execution_context.cancellation.is_cancelled():
            execution_context.events.emit("research_cancelled", {"read_only": True})
            raise asyncio.CancelledError("archive research cancelled")
        source_ids = tuple(request.source_item_ids or (
            item.source_item_id for item in request.source_items
        ))
        bound_tools = BoundCorpusTools(
            self.corpus_tools,
            request.project_id,
            source_ids,
            source_items=request.source_items,
        )
        read_meter = CorpusReadMeter(bound_tools.materialized_source_items)
        setattr(bound_tools, "_corpus_read_meter", read_meter)
        request = _materialize_request(request, bound_tools)
        execution_context.events.emit("research_started", {"read_only": True})
        manifest = bound_tools.corpus_manifest()
        role_max_calls = self._adaptive_role_budget(manifest["local_unit_count"])
        execution_context.events.emit("research_fanout_planned", {
            "read_only": True,
            "local_unit_count": manifest["local_unit_count"],
            "role_max_calls": role_max_calls,
        })
        trace = ContextResearchTraceCollector(
            request.request_id,
            project_id=request.project_id,
            output_path=self.trace_output_path,
        )
        read_meter.set_observation_sink(trace.record_corpus_read)
        trace.record_corpus_read({}, read_meter.snapshot())
        if trace.output_path is not None:
            trace.persist()
        tracker = self._build_delegation_tracker(execution_context, trace, bound_tools)
        agent = self.build_agent(
            output_type=LeadResearchResult,
            delegation_tracker=tracker,
            role_max_calls=role_max_calls,
        )
        run_adjudication = self._build_adjudication_runner(execution_context)
        async def run_lead(
            selected_agent: Any,
            selected_prompt: str,
            selected_tools: BoundCorpusTools,
            *,
            message_history: Any = None,
        ) -> Any:
            task = asyncio.create_task(self._run_lead(
                selected_agent,
                selected_prompt,
                selected_tools,
                message_history=message_history,
            ))
            return await await_with_cancellation(task, execution_context)

        try:
            result = await run_lead(agent, initial_prompt(request), bound_tools)
        except asyncio.CancelledError:
            execution_context.events.emit("research_cancelled", {"read_only": True})
            raise
        except Exception as error:
            draft = await self._retain_after_lead_failure(
                error, agent, bound_tools, tracker, request, execution_context,
                run_lead, trace,
            )
            draft = self._attach_read_metric(draft, read_meter)
            self.last_trace_snapshot = trace.snapshot()
            return draft
        if execution_context.cancellation.is_cancelled():
            raise asyncio.CancelledError("archive research cancelled")
        findings = result.output if isinstance(result.output, ContextResearchFindings) else ContextResearchFindings()
        try:
            draft = await self.run_coordinator.finalize(
                initial_result=result,
                agent=agent,
                bound_tools=bound_tools,
                tracker=tracker,
                request=request,
                execution_context=execution_context,
                run_lead=run_lead,
                trace=trace,
                run_adjudication=run_adjudication,
            )
        except Exception as error:
            execution_context.events.emit(
                "research_failed",
                {
                    "read_only": True,
                    "stage": "compilation",
                    "error_type": type(error).__name__,
                    "partial_artifact_retained": True,
                },
            )
            draft = self._retain_after_finalization_failure(
                error, findings, tracker, request, trace,
            )
            draft = self._attach_read_metric(draft, read_meter)
            self.last_trace_snapshot = trace.snapshot()
            return draft
        draft = self._attach_read_metric(draft, read_meter)
        self.last_trace_snapshot = trace.snapshot()
        compiler_diagnostics = draft.diagnostics.get("compiler", {})
        execution_context.events.emit("research_completed", {
            "read_only": True,
            "compiled": True,
            "published_counts": compiler_diagnostics.get("published_counts", {}),
            "rejected_source_item_count": len(
                compiler_diagnostics.get("rejected_source_item_ids", ())
            ),
            "run_status": draft.diagnostics.get("run", {}).get("status"),
            "publishable": draft.diagnostics.get("run", {}).get("publishable"),
        })
        return draft

    @staticmethod
    def _attach_read_metric(draft: Any, meter: CorpusReadMeter) -> Any:
        diagnostics = dict(getattr(draft, "diagnostics", {}) or {})
        diagnostics["corpus_read_amplification"] = meter.snapshot()
        return draft.model_copy(update={"diagnostics": diagnostics})


ContextResearchHarnessBackend = PydanticAIContextResearchBackend

__all__ = [
    "HARNESS_AVAILABLE",
    "HARNESS_COMPATIBILITY_NOTE",
    "PydanticAIContextResearchBackend",
    "ContextResearchHarnessBackend",
    "LEAD_MAX_OUTPUT_TOKENS",
    "LEAD_OUTPUT_TOKEN_LIMIT",
    "MAX_ROLE_CALLS_PER_RUN",
    "REQUIRED_ROLE_NAMES",
    "SUBAGENT_MAX_OUTPUT_TOKENS",
    "SUBAGENT_OUTPUT_TOKEN_LIMIT",
]
