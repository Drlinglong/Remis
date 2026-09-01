"""Delegation tracking and result helpers for the Context Research Harness."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic_ai.usage import RunUsage

from scripts.core.services.context_research_shard_memo import (
    ShardMemo,
    ShardMemoCollection,
    ShardMemoCollector,
)
from scripts.core.services.context_research_ids import ShortIdRegistry
from scripts.core.services.context_research_trace_ledger import (
    ContextResearchTraceCollector,
    usage_record_from_run_usage,
)


REQUIRED_ROLE_NAMES = (
    "cartographer", "event_investigator", "archive_lore", "evidence_auditor",
)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _model_label(model: Any) -> str:
    for name in ("model_name", "model_id", "name"):
        value = getattr(model, name, None)
        if isinstance(value, str) and value.strip():
            return value
    return type(model).__name__


def _result_usage(result: Any) -> Any:
    usage = getattr(result, "usage", {})
    return usage() if callable(usage) else usage


def _result_messages(result: Any, *, full: bool = False) -> Any:
    name = "all_messages" if full else "new_messages"
    accessor = getattr(result, name, None)
    if callable(accessor):
        return accessor()
    fallback = getattr(result, "all_messages", None)
    return fallback() if callable(fallback) else ()


_FINDING_COLLECTIONS = (
    "archive_narratives", "entities", "event_chains", "reference_assets", "unresolved",
)


def _compact_memo_receipt(memo: ShardMemo) -> dict[str, Any]:
    """Summarize an accepted memo without copying claims or evidence."""

    receipt = {
        "role": memo.role,
        "shard_ids": list(memo.shard_ids),
        "core_local_unit_count": len(memo.core_local_unit_ids),
        "overlap_local_unit_count": len(memo.overlap_local_unit_ids),
        "finding_counts": {
            kind: sum(
                len(unit.entity_mentions) if kind == "entities"
                else len(getattr(unit.findings, kind))
                for unit in memo.units
            )
            for kind in _FINDING_COLLECTIONS
        },
        "collection_accepted": True,
    }
    decision_index = _memo_decision_index(memo)
    if decision_index["event_chains"] or decision_index["entities"]:
        receipt["decision_index"] = decision_index
    return receipt


def _memo_decision_index(memo: ShardMemo) -> dict[str, list[dict[str, Any]]]:
    """Expose only the identities Lead needs for cross-shard sparse decisions."""

    events: dict[tuple[str, int], dict[str, Any]] = {}
    entities: dict[str, dict[str, Any]] = {}
    for unit in memo.units:
        if unit.ownership != "core" or unit.disposition != "modeled":
            continue
        for finding in unit.findings.event_chains:
            key = (finding.chain_id, finding.sequence)
            entry = events.setdefault(key, {
                "finding_id": finding.chain_id,
                "sequence": finding.sequence,
                "local_unit_ids": [],
                "label": _compact_label(finding.event),
            })
            entry["local_unit_ids"] = list(dict.fromkeys((
                *entry["local_unit_ids"], *finding.local_unit_ids,
            )))
        for finding in unit.entity_mentions:
            entry = entities.setdefault(finding.entity_id, {
                "finding_id": finding.entity_id,
                "name": finding.name,
                "entity_type": finding.entity_type,
                "reported_by_unit_ids": [],
            })
            entry["reported_by_unit_ids"] = list(dict.fromkeys((
                *entry["reported_by_unit_ids"], unit.local_unit_id,
            )))
    return {
        "event_chains": [events[key] for key in sorted(events)],
        "entities": [entities[key] for key in sorted(entities)],
    }


def _compact_label(value: str, limit: int = 180) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[: limit - 1] + "…"


class CompactChildRunResult:
    """Expose a receipt to Harness while retaining the real run metadata."""

    def __init__(self, result: Any, memo: ShardMemo) -> None:
        self._result = result
        self.output = _compact_memo_receipt(memo)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._result, name)


class DelegationTracker:
    """Count completed role calls and persist each child memo independently."""

    def __init__(
        self,
        events: Any,
        trace: ContextResearchTraceCollector | None = None,
        memo_collector: ShardMemoCollector | None = None,
        id_registry: ShortIdRegistry | None = None,
    ) -> None:
        self.events = events
        self.trace = trace
        self.successes = {role: 0 for role in REQUIRED_ROLE_NAMES}
        self.attempts = {role: 0 for role in REQUIRED_ROLE_NAMES}
        self.bound = False
        self.memo_collector = memo_collector
        self.id_registry = id_registry
        self.memos: list[ShardMemo] = []
        self._last_accepted_memo: ShardMemo | None = None

    def mark_bound(self) -> None:
        self.bound = True

    def wrap(self, agent: Any, role: str) -> "TrackedChildAgent":
        return TrackedChildAgent(agent, role, self)

    def accept_memo(
        self,
        *,
        role: str,
        expected_shard_ids: tuple[str, ...],
        lease: Any,
        output: Any,
    ) -> bool:
        """Validate and retain a typed child result before it counts as success."""

        if self.memo_collector is None:
            return True
        self._last_accepted_memo = None
        payload = output.model_dump(mode="python") if isinstance(output, ShardMemo) else dict(output or {})
        if self.id_registry is not None:
            payload, _ = self.id_registry.normalize_memo_payload(payload)
        try:
            memo = ShardMemo.model_validate(payload)
        except Exception as error:
            self.events.emit("research_role_rejected", {
                "role": role, "reason": "invalid_typed_memo",
                "error_type": type(error).__name__, "read_only": True,
            })
            return False
        # A child is allowed to return a sparse memo.  The lead may have
        # delegated several shards while the child only managed to inspect a
        # non-empty subset.  Retain that evidence so the collector can expose
        # the exact gap for one bounded completion pass.  Ownership is still
        # constrained to the task lease; the manifest-backed collector remains
        # authoritative for shard/unit ownership diagnostics.
        matches_lease = (
            memo.role == role
            and set(memo.shard_ids) <= set(expected_shard_ids)
            and bool(memo.shard_ids)
            and set(memo.core_local_unit_ids) <= set(lease.core_local_unit_ids)
            and set(memo.overlap_local_unit_ids) <= set(lease.overlap_local_unit_ids)
        )
        if matches_lease:
            self.memo_collector.add(memo)
            self.memos.append(memo)
            self._last_accepted_memo = memo
        if not matches_lease:
            self.events.emit("research_role_rejected", {
                "role": role, "reason": "memo_outside_delegation_lease",
                "read_only": True, "partial_artifact_retained_in_trace": True,
            })
        return matches_lease

    def collect_memos(self) -> ShardMemoCollection | None:
        return self.memo_collector.collect() if self.memo_collector is not None else None

    @property
    def missing_roles(self) -> tuple[str, ...]:
        return tuple(role for role in REQUIRED_ROLE_NAMES if self.successes.get(role, 0) < 1)

    @property
    def last_accepted_memo(self) -> ShardMemo | None:
        """Return the memo accepted by the most recent typed child run."""

        return self._last_accepted_memo

    def start(self, role: str, task: Any, model: Any) -> tuple[str, str, str]:
        self.attempts[role] = self.attempts.get(role, 0) + 1
        shard = f"{role}-{self.attempts[role]}"
        started_at = _now()
        delegation_id = f"delegation-{shard}"
        if self.trace is not None:
            self.trace.record_delegation(
                role=role,
                shard=shard,
                task=task,
                status="running",
                model=_model_label(model),
                delegation_id=delegation_id,
                started_at=started_at,
            )
            self._flush_trace()
        return delegation_id, shard, started_at

    def finish(
        self,
        *,
        role: str,
        model: Any,
        task: Any,
        delegation_id: str,
        shard: str,
        started_at: str,
        result: Any | None,
        error: BaseException | None,
        accepted: bool = True,
        failed_usage: RunUsage | None = None,
    ) -> None:
        finished_at = _now()
        status = "completed" if error is None and accepted else (
            "rejected" if error is None else (
            "cancelled" if type(error).__name__ == "CancelledError" else "failed"
        ))
        if error is None and accepted:
            self.successes[role] = self.successes.get(role, 0) + 1
            self.events.emit("research_role_completed", {
                "role": role,
                "successful_runs": self.successes[role],
                "shard": shard,
            })
        if self.trace is None:
            return
        memo = getattr(result, "output", None) if result is not None else None
        self.trace.record_delegation(
            role=role,
            shard=shard,
            task=task,
            status=status,
            model=_model_label(model),
            delegation_id=delegation_id,
            started_at=started_at,
            finished_at=finished_at,
            child_memo=memo,
        )
        if error is not None:
            self.trace.record_error(
                error, stage="subagent", role=role, shard=shard,
            )
        if result is not None:
            self.trace.record_usage(usage_record_from_run_usage(
                _result_usage(result),
                scope="subagent",
                role=role,
                shard=shard,
                model=_model_label(model),
                status=status,
                started_at=started_at,
                finished_at=finished_at,
            ))
            self.trace.record_message_history(
                _result_messages(result), role=role, shard=shard,
                model=_model_label(model),
            )
        elif error is not None:
            if failed_usage is not None and failed_usage.requests:
                self.trace.record_usage(usage_record_from_run_usage(
                    failed_usage,
                    scope="subagent",
                    role=role,
                    shard=shard,
                    model=_model_label(model),
                    status=status,
                    started_at=started_at,
                    finished_at=finished_at,
                ))
            self.trace.record_tool_activity(
                tool="delegate_task",
                role=role,
                shard=shard,
                model=_model_label(model),
                status=status,
                metadata={"error_type": type(error).__name__},
                started_at=started_at,
                finished_at=finished_at,
            )
        self._flush_trace()

    def _flush_trace(self) -> None:
        if self.trace is not None and self.trace.output_path is not None:
            self.trace.persist()


class TrackedChildAgent:
    """Duck-typed agent proxy that records a complete isolated child run."""

    def __init__(self, agent: Any, role: str, tracker: DelegationTracker) -> None:
        self._agent = agent
        self._role = role
        self._tracker = tracker

    async def run(self, task: Any = None, *args: Any, **kwargs: Any) -> Any:
        delegation_id, shard, started_at = self._tracker.start(
            self._role, task, self._agent.model,
        )
        run_usage = RunUsage()
        try:
            deps = kwargs.get("deps")
            validate_task = getattr(deps, "validate_delegation_task", None)
            shard_ids: tuple[str, ...] = ()
            lease = None
            if callable(validate_task):
                shard_ids = tuple(validate_task(task))
            if shard_ids:
                lease = deps.shard_lease(shard_ids)
                kwargs["deps"] = deps.owned_shard_view(shard_ids)
            kwargs["usage"] = run_usage
            result = await self._agent.run(task, *args, **kwargs)
            accepted = True
            if self._tracker.memo_collector is not None:
                if lease is None:
                    accepted = False
                    self._tracker.events.emit("research_role_rejected", {
                        "role": self._role,
                        "reason": "missing_exact_shard_lease",
                        "read_only": True,
                    })
                else:
                    accepted = self._tracker.accept_memo(
                    role=self._role,
                    expected_shard_ids=shard_ids,
                    lease=lease,
                    output=getattr(result, "output", None),
                    )
        except BaseException as error:
            self._tracker.finish(
                role=self._role, model=self._agent.model, task=task,
                delegation_id=delegation_id, shard=shard, started_at=started_at,
                result=None, error=error, failed_usage=run_usage,
            )
            raise
        self._tracker.finish(
            role=self._role, model=self._agent.model, task=task,
            delegation_id=delegation_id, shard=shard, started_at=started_at,
            result=result, error=None, accepted=accepted,
        )
        memo = self._tracker.last_accepted_memo
        if accepted and memo is not None:
            return CompactChildRunResult(result, memo)
        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)


__all__ = [
    "DelegationTracker",
    "CompactChildRunResult",
    "REQUIRED_ROLE_NAMES",
    "TrackedChildAgent",
]
