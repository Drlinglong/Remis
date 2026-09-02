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
MAX_MEMO_CONTRACT_RETRIES = 1


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
        memo_contract_retries: int = MAX_MEMO_CONTRACT_RETRIES,
    ) -> None:
        if not 0 <= memo_contract_retries <= MAX_MEMO_CONTRACT_RETRIES:
            raise ValueError("memo_contract_retries must be zero or one")
        self.events = events
        self.trace = trace
        self.successes = {role: 0 for role in REQUIRED_ROLE_NAMES}
        self.attempts = {role: 0 for role in REQUIRED_ROLE_NAMES}
        self.memo_retries = {role: 0 for role in REQUIRED_ROLE_NAMES}
        self.memo_contract_retries = memo_contract_retries
        self.bound = False
        self.memo_collector = memo_collector
        self.id_registry = id_registry
        self.memos: list[ShardMemo] = []
        self._last_accepted_memo: ShardMemo | None = None
        self._last_rejection_reason: str | None = None

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
        self._last_rejection_reason = None
        try:
            payload = (
                output.model_dump(mode="python")
                if isinstance(output, ShardMemo) else dict(output or {})
            )
        except Exception as error:
            self._last_rejection_reason = "invalid_typed_memo"
            self.events.emit("research_role_rejected", {
                "role": role, "reason": self._last_rejection_reason,
                "error_type": type(error).__name__, "read_only": True,
            })
            return False
        id_rejections = ()
        if self.id_registry is not None:
            payload, id_rejections = self.id_registry.normalize_memo_payload(payload)
        if id_rejections:
            self._last_rejection_reason = "invalid_memo_ids"
            self.events.emit("research_role_rejected", {
                "role": role, "reason": self._last_rejection_reason,
                "id_rejection_codes": sorted({item.code for item in id_rejections}),
                "id_rejection_kinds": sorted({item.kind for item in id_rejections}),
                "id_rejection_count": len(id_rejections),
                "read_only": True,
            })
            return False
        try:
            memo = ShardMemo.model_validate(payload)
        except Exception as error:
            self._last_rejection_reason = "invalid_typed_memo"
            self.events.emit("research_role_rejected", {
                "role": role, "reason": self._last_rejection_reason,
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
            self._last_rejection_reason = "memo_outside_delegation_lease"
            self.events.emit("research_role_rejected", {
                "role": role, "reason": self._last_rejection_reason,
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

    @property
    def last_rejection_reason(self) -> str | None:
        """Return the bounded-contract reason for the most recent rejection."""

        return self._last_rejection_reason

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
    """Duck-typed agent proxy with one bounded memo-contract retry."""

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
                    self._tracker._last_rejection_reason = "missing_exact_shard_lease"
                    self._tracker.events.emit("research_role_rejected", {
                        "role": self._role,
                        "reason": self._tracker.last_rejection_reason,
                        "read_only": True,
                    })
                else:
                    accepted = self._tracker.accept_memo(
                        role=self._role,
                        expected_shard_ids=shard_ids,
                        lease=lease,
                        output=getattr(result, "output", None),
                    )
            retry_count = 0
            while (
                not accepted
                and lease is not None
                and retry_count < self._tracker.memo_contract_retries
            ):
                if not _memo_retry_budget_available(run_usage, kwargs):
                    self._tracker.events.emit("research_role_retry_skipped", {
                        "role": self._role,
                        "shard_ids": list(shard_ids),
                        "reason": "memo_retry_budget_exhausted",
                        "read_only": True,
                    })
                    break
                retry_count += 1
                reason = self._tracker.last_rejection_reason or "memo_contract_rejected"
                retry_task = _memo_contract_retry_task(
                    task, self._role, shard_ids, lease, deps,
                )
                self._tracker.memo_retries[self._role] = (
                    self._tracker.memo_retries.get(self._role, 0) + 1
                )
                self._tracker.events.emit("research_role_retry_scheduled", {
                    "role": self._role,
                    "shard_ids": list(shard_ids),
                    "retry_number": retry_count,
                    "reason": reason,
                    "read_only": True,
                })
                if self._tracker.trace is not None:
                    self._tracker.trace.record_tool_activity(
                        tool="memo_contract_retry",
                        status="scheduled",
                        role=self._role,
                        shard=shard,
                        model=_model_label(self._agent.model),
                        metadata={
                            "retry_number": retry_count,
                            "reason": reason,
                            "shard_ids": list(shard_ids),
                        },
                    )
                    self._tracker._flush_trace()
                retry_kwargs = dict(kwargs)
                retry_kwargs["usage"] = run_usage
                result = await self._agent.run(retry_task, *args, **retry_kwargs)
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
    "MAX_MEMO_CONTRACT_RETRIES",
    "REQUIRED_ROLE_NAMES",
    "TrackedChildAgent",
]


def _memo_contract_retry_task(
    task: Any,
    role: str,
    shard_ids: tuple[str, ...],
    lease: Any,
    deps: Any,
) -> str:
    """Make a corrective prompt without widening the original lease."""

    registry = getattr(getattr(deps, "_bound", None), "id_registry", None)
    core_ids = tuple(getattr(lease, "core_local_unit_ids", ()))
    overlap_ids = tuple(getattr(lease, "overlap_local_unit_ids", ()))
    if registry is not None:
        core_ids = tuple(registry.modelize_ids(core_ids, "unit"))
        overlap_ids = tuple(registry.modelize_ids(overlap_ids, "unit"))
    return (
        f"{task or ''}\n\n"
        "[MEMO CONTRACT RETRY]\n"
        "上一份 child memo 未通过宿主的确定性契约校验。只在原 lease 内重做一次，"
        f"role 必须是 {role!r}，shard_ids 必须严格为 {list(shard_ids)!r}；"
        f"core_local_unit_ids 只能来自 {list(core_ids)!r}，"
        f"overlap_local_unit_ids 只能来自 {list(overlap_ids)!r}。"
        "请重新读取同一批 exact shard，并逐一返回 core unit；不要添加其他 shard、"
        "unit 或 finding。所有 event local_unit_ids 只能使用 leased core unit 的原样短 ID；"
        "所有 evidence.source_item_ids 只能填写工具输出中原样的 S### 短 ID，不能把标题、"
        "描述或其它文字拼接到 ID 中。不要用邻接关系猜测 ID，不要用 canonical ID 替换工具返回的短 ID。"
    )


def _memo_retry_budget_available(run_usage: RunUsage, kwargs: dict[str, Any]) -> bool:
    """Reserve a provider request for the corrective memo pass when possible."""

    limit = getattr(kwargs.get("usage_limits"), "request_limit", None)
    requests = getattr(run_usage, "requests", 0) or 0
    return not isinstance(limit, int) or requests < limit
