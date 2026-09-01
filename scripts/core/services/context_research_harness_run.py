"""Run support for the developer Context Research Harness adapter.

This module owns bounded completion, targeted repair, and developer tracing.
It does not build agents, read files, publish drafts, or own Remis task state.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from scripts.core.services.context_research_compiler import (
    ContextResearchDraftCompiler,
    ContextResearchFindings,
)
from scripts.core.services.context_research_delegation import (
    DelegationTracker,
    REQUIRED_ROLE_NAMES,
    TrackedChildAgent,
    _model_label,
    _result_messages,
    _result_usage,
)
from scripts.core.services.context_research_finding_merge import (
    apply_targeted_repairs,
    merge_findings,
)
from scripts.core.services.context_research_finding_reducer import reduce_findings
from scripts.core.services.context_research_route_resolver import apply_delivery_routes
from scripts.core.services.context_research_lead_decisions import (
    LeadResearchDecisions,
    LeadResearchResult,
)
from scripts.core.services.context_research_prompts import (
    completion_prompt,
    targeted_repair_prompt,
)
from scripts.core.services.context_research_repair_policy import (
    MAX_REPAIR_ATTEMPTS,
    RepairPacket,
    build_repair_packet,
)
from scripts.core.services.context_research_shard_memo import ShardMemoCollection
from scripts.core.services.context_research_trace_ledger import (
    ContextResearchTraceCollector,
    usage_record_from_run_usage,
)


def _merge_lead_results(
    first: LeadResearchResult,
    second: LeadResearchResult,
) -> LeadResearchResult:
    """Accumulate sparse decisions; later duplicates are rejected by the schema."""

    first_decisions = first.decisions
    second_decisions = second.decisions
    decisions = LeadResearchDecisions(
        event_members=(*first_decisions.event_members, *second_decisions.event_members),
        entity_merges=(*first_decisions.entity_merges, *second_decisions.entity_merges),
        discards=(*first_decisions.discards, *second_decisions.discards),
        patches=(*first_decisions.patches, *second_decisions.patches),
    )
    return LeadResearchResult(
        decisions=decisions,
        repair_findings=(*first.repair_findings, *second.repair_findings),
        notes=second.notes or first.notes,
    )


def _coerce_lead_output(output: Any) -> tuple[LeadResearchResult, ContextResearchFindings]:
    """Accept legacy test findings without making them the production Lead contract."""

    if isinstance(output, LeadResearchResult):
        return output, ContextResearchFindings()
    if isinstance(output, ContextResearchFindings):
        return LeadResearchResult(), output
    try:
        return LeadResearchResult.model_validate(output), ContextResearchFindings()
    except Exception:
        return LeadResearchResult(), ContextResearchFindings.model_validate(output)


def _with_memo_collection(
    tracker: DelegationTracker,
    lead: LeadResearchResult,
    legacy_findings: ContextResearchFindings,
) -> ContextResearchFindings:
    collection = tracker.collect_memos()
    if collection is None:
        return legacy_findings
    findings = reduce_findings(collection, lead)
    findings = merge_findings(findings, legacy_findings)
    findings = apply_delivery_routes(collection, findings)
    diagnostics = dict(findings.diagnostics or {})
    diagnostics["memo_collection"] = {
        "complete": collection.complete,
        "unit_count": len(collection.units),
        "missing_core_local_unit_ids": list(collection.missing_core_local_unit_ids),
        "missing_shard_ids": list(collection.missing_shard_ids),
        "duplicate_core_local_unit_ids": list(collection.duplicate_core_local_unit_ids),
        "conflict_local_unit_ids": list(collection.conflict_local_unit_ids),
        "conflicting_finding_ids": list(collection.conflicting_finding_ids),
        "evidence_conflicts": list(collection.evidence_conflicts),
        "unknown_shard_ids": list(collection.unknown_shard_ids),
        "invalid_unit_ownership": list(collection.invalid_unit_ownership),
    }
    return findings.model_copy(update={"diagnostics": diagnostics})


def with_delegation_status(
    findings: ContextResearchFindings,
    tracker: DelegationTracker,
    completion_attempted: bool,
    gap_completion_attempted: bool = False,
) -> ContextResearchFindings:
    diagnostics = dict(findings.diagnostics)
    missing = tracker.missing_roles
    diagnostics["delegation"] = {
        "status": "complete" if not missing else "incomplete",
        "required_roles": list(REQUIRED_ROLE_NAMES),
        "successful_roles": [role for role in REQUIRED_ROLE_NAMES if role not in missing],
        "missing_roles": list(missing),
        "successful_runs": dict(tracker.successes),
        "attempted_runs": dict(tracker.attempts),
        "completion_attempted": completion_attempted,
        "gap_completion_attempted": gap_completion_attempted,
    }
    return findings.model_copy(update={"diagnostics": diagnostics})


RunLead = Callable[..., Awaitable[Any]]


class ContextResearchRunCoordinator:
    """Complete required roles, compile, and run up to two narrow repairs."""

    def __init__(
        self,
        compiler: ContextResearchDraftCompiler,
        *,
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
    ) -> None:
        if not 0 <= max_repair_attempts <= MAX_REPAIR_ATTEMPTS:
            raise ValueError("max_repair_attempts must be between zero and two")
        self.compiler = compiler
        self.max_repair_attempts = max_repair_attempts

    async def finalize(
        self,
        *,
        initial_result: Any,
        agent: Any,
        bound_tools: Any,
        tracker: DelegationTracker,
        request: Any,
        execution_context: Any,
        run_lead: RunLead,
        trace: ContextResearchTraceCollector | None = None,
    ) -> Any:
        model = _model_label(getattr(agent, "model", None))
        lead, legacy_findings = self._record_lead(
            initial_result, execution_context, trace, "lead", 1, model,
        )
        latest_result = initial_result
        completion_attempted = False
        if tracker.bound and tracker.missing_roles:
            completion_attempted = True
            lead, completion_legacy, latest_result = await self._complete_roles(
                lead, latest_result, agent, bound_tools, tracker, request,
                execution_context, run_lead, trace,
            )
            legacy_findings = merge_findings(legacy_findings, completion_legacy)
        gap_completion_attempted = False
        collection = tracker.collect_memos()
        if (
            tracker.bound
            and not tracker.missing_roles
            and collection is not None
            and collection.missing_shard_ids
        ):
            # A child may have returned a valid partial memo.  Give the Lead
            # one exact, bounded gap pass; never retry this pass in a loop.
            gap_completion_attempted = True
            lead, gap_legacy, latest_result = await self._complete_gap(
                lead, latest_result, agent, bound_tools, tracker,
                collection.missing_shard_ids, request, execution_context,
                run_lead, trace,
            )
            legacy_findings = merge_findings(legacy_findings, gap_legacy)
        findings = _with_memo_collection(tracker, lead, legacy_findings)
        findings = with_delegation_status(
            findings, tracker, completion_attempted or gap_completion_attempted,
            gap_completion_attempted,
        )
        draft = self.compiler.compile(
            findings, request, id_registry=getattr(bound_tools, "id_registry", None),
        )
        repair_attempts = 0
        packet = build_repair_packet(draft.diagnostics, findings, request=request)
        while packet.model_call_allowed and repair_attempts < self.max_repair_attempts:
            repair_attempts += 1
            if trace is not None:
                trace.record_repair(packet=packet, attempt=repair_attempts)
                self._flush(trace)
            repair_result = await run_lead(
                agent,
                targeted_repair_prompt(
                    packet, request.description_language,
                    id_registry=getattr(bound_tools, "id_registry", None),
                ),
                bound_tools,
                message_history=_result_messages(latest_result, full=True),
            )
            repair_lead, repair_findings = self._record_lead(
                repair_result, execution_context, trace, "repair", repair_attempts, model,
            )
            if trace is not None:
                trace.record_repair(
                    output={
                        "lead": repair_lead.model_dump(mode="json"),
                        "legacy_findings": repair_findings.model_dump(mode="json"),
                    },
                    attempt=repair_attempts,
                )
            findings = reduce_findings(findings, repair_lead)
            if any(
                getattr(repair_findings, kind)
                for kind in (
                    "archive_narratives", "entities", "event_chains",
                    "reference_assets", "unresolved",
                )
            ):
                findings = apply_targeted_repairs(findings, repair_findings, packet)
            draft = self.compiler.compile(
                findings, request, id_registry=getattr(bound_tools, "id_registry", None),
            )
            latest_result = repair_result
            packet = build_repair_packet(
                draft.diagnostics, findings, request=request, attempt=repair_attempts,
            )
        return self._finish(
            draft, findings, tracker, packet, repair_attempts, trace,
        )

    def finalize_partial(
        self,
        *,
        findings: ContextResearchFindings,
        tracker: DelegationTracker,
        request: Any,
        completion_attempted: bool,
        trace: ContextResearchTraceCollector | None = None,
    ) -> Any:
        """Compile retained findings when the lead cannot produce a final result."""

        findings = _with_memo_collection(tracker, LeadResearchResult(), findings)
        findings = with_delegation_status(findings, tracker, completion_attempted)
        draft = self.compiler.compile(
            findings, request, id_registry=getattr(tracker, "id_registry", None),
        )
        packet = build_repair_packet(draft.diagnostics, findings, request=request)
        return self._finish(draft, findings, tracker, packet, 0, trace)

    async def _complete_roles(
        self,
        lead: LeadResearchResult,
        latest_result: Any,
        agent: Any,
        bound_tools: Any,
        tracker: DelegationTracker,
        request: Any,
        execution_context: Any,
        run_lead: RunLead,
        trace: ContextResearchTraceCollector | None,
    ) -> tuple[LeadResearchResult, ContextResearchFindings, Any]:
        prompt = completion_prompt(tracker.missing_roles)
        try:
            result = await run_lead(
                agent, prompt, bound_tools,
                message_history=_result_messages(latest_result, full=True),
            )
            completed, legacy = self._record_lead(
                result, execution_context, trace, "completion", 1,
                _model_label(getattr(agent, "model", None)),
            )
            return _merge_lead_results(lead, completed), legacy, result
        except Exception as error:
            execution_context.events.emit("research_completion_failed", {
                "read_only": True,
                "error_type": type(error).__name__,
                "missing_roles": list(tracker.missing_roles),
            })
            return lead, ContextResearchFindings(), latest_result

    async def _complete_gap(
        self,
        lead: LeadResearchResult,
        latest_result: Any,
        agent: Any,
        bound_tools: Any,
        tracker: DelegationTracker,
        missing_shard_ids: tuple[str, ...],
        request: Any,
        execution_context: Any,
        run_lead: RunLead,
        trace: ContextResearchTraceCollector | None,
    ) -> tuple[LeadResearchResult, ContextResearchFindings, Any]:
        """Run the single exact-shard completion pass for missing coverage."""

        del request
        prompt = completion_prompt(
            tracker.missing_roles, missing_shard_ids=missing_shard_ids,
        )
        try:
            result = await run_lead(
                agent, prompt, bound_tools,
                message_history=_result_messages(latest_result, full=True),
            )
            completed, legacy = self._record_lead(
                result, execution_context, trace, "gap_completion", 1,
                _model_label(getattr(agent, "model", None)),
            )
            return _merge_lead_results(lead, completed), legacy, result
        except Exception as error:
            execution_context.events.emit("research_completion_failed", {
                "read_only": True,
                "error_type": type(error).__name__,
                "missing_roles": list(tracker.missing_roles),
                "missing_shard_ids": list(missing_shard_ids),
                "completion_kind": "gap",
            })
            return lead, ContextResearchFindings(), latest_result

    @staticmethod
    def _record_lead(
        result: Any,
        execution_context: Any,
        trace: ContextResearchTraceCollector | None,
        scope: str,
        attempt: int,
        model: str,
    ) -> tuple[LeadResearchResult, ContextResearchFindings]:
        usage = _result_usage(result)
        execution_context.usage.record(
            "context_research", scope="harness_run_observed", phase=scope, attempt=attempt,
            model=model,
            usage=usage_record_from_run_usage(usage, scope=scope, model=model).to_dict(),
        )
        lead, findings = _coerce_lead_output(result.output)
        if trace is not None:
            trace.record_usage(usage_record_from_run_usage(usage, scope=scope, model=model))
            history = trace.record_message_history(_result_messages(result), model=model)
            if history["planning"]:
                trace.record_plan(history["planning"], status="completed")
            trace.record_findings({
                "lead_decisions": lead.model_dump(mode="json"),
                "legacy_findings": findings.model_dump(mode="json"),
            })
            ContextResearchRunCoordinator._flush(trace)
        return lead, findings

    @staticmethod
    def _finish(
        draft: Any,
        findings: ContextResearchFindings,
        tracker: DelegationTracker,
        packet: RepairPacket,
        repair_attempts: int,
        trace: ContextResearchTraceCollector | None,
    ) -> Any:
        delegation_incomplete = bool(tracker.missing_roles) if tracker.bound else False
        repairable_targets = tuple(
            item for item in packet.targets if item.classification == "repairable"
        )
        # Compiler-safe degradation (for example, dropping an optional entity
        # link whose target was itself rejected) must not block the otherwise
        # complete archive when no grounded repair call can be made.  A repair
        # that remains after an actual attempt is still a publication blocker.
        repair_incomplete = packet.systemic_corruption or bool(
            repairable_targets and (packet.model_call_allowed or repair_attempts > 0)
        )
        nonblocking_repair_targets = (
            len(repairable_targets) if repairable_targets and not repair_incomplete else 0
        )
        coverage_blocked = packet.coverage.blocks_key_shard_gate
        memo_collection = dict(findings.diagnostics.get("memo_collection", {}) or {})
        memo_incomplete = memo_collection.get("complete") is False
        incomplete = (
            delegation_incomplete or repair_incomplete or coverage_blocked
            or memo_incomplete
        )
        diagnostics = dict(draft.diagnostics)
        diagnostics["run"] = {
            "status": "incomplete" if incomplete else "complete",
            "publishable": not incomplete,
            "repair_attempts": repair_attempts,
            "repair_remaining": repair_incomplete,
            "nonblocking_repair_target_count": nonblocking_repair_targets,
            "memo_collection_complete": not memo_incomplete,
            "coverage": packet.coverage.model_dump(mode="json"),
        }
        draft = draft.model_copy(update={"diagnostics": diagnostics})
        if trace is not None:
            trace.record_findings(findings)
            trace.record_compiler_diagnostics(diagnostics)
            trace.record_final_draft(draft)
            ContextResearchRunCoordinator._flush(trace)
        return draft

    @staticmethod
    def _flush(trace: ContextResearchTraceCollector) -> None:
        if trace.output_path is not None:
            trace.persist()


__all__ = [
    "ContextResearchRunCoordinator",
    "DelegationTracker",
    "REQUIRED_ROLE_NAMES",
    "TrackedChildAgent",
    "apply_targeted_repairs",
    "merge_findings",
]
