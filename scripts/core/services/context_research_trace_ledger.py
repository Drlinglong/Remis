"""Persistable trace and usage ledger for one context-research run.

The ledger is an observability boundary, not a workflow engine.  It records
the lead plan, bounded delegations, tool activity, model findings, compiler
diagnostics, repair artifacts, and final draft so a developer can audit the
whole tree after a run.  It deliberately has no checkpoint, resume, or model
execution behavior.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping

from scripts.core.services.context_research_trace_messages import (
    _bounded_safe,
    _decode_tool_args,
    _message_timestamp,
    _part_timestamp,
    _redact_error_message,
    _safe,
    _tool_result_digest,
    extract_message_history_trace,
)
from scripts.core.services.context_research_trace_usage import (
    UsageRecord,
    duration_ms_between as _duration_ms,
    normalize_usage,
    normalize_usage as _normalize_usage,
    summarize_usage,
    usage_group_summary as _usage_group_summary,
    usage_record_from_run_usage,
)


_MISSING = object()


class ContextResearchTraceCollector:
    """Collect one run's trace and atomically persist it as UTF-8 JSON."""

    schema_version = "context-research-trace-ledger-v1"

    def __init__(
        self,
        trace_id: str,
        *,
        project_id: str | None = None,
        output_path: str | os.PathLike[str] | None = None,
        started_at: str | None = None,
    ) -> None:
        if not trace_id.strip():
            raise ValueError("trace_id must not be blank")
        self.output_path = Path(output_path) if output_path is not None else None
        now = started_at or _now()
        self._state: dict[str, Any] = {
            "schema_version": self.schema_version,
            "trace_id": trace_id,
            "project_id": project_id,
            "started_at": now,
            "updated_at": now,
            "plan": None,
            "delegations": [],
            "tool_activity": [],
            "corpus_read": {
                "schema_version": "corpus-read-amplification-v1",
                "metric_name": "Corpus Read Amplification",
                "numerator_tokens": 0,
                "denominator_tokens": 0,
                "value": None,
                "complete": True,
                "observations": [],
            },
            "planning_events": [],
            "lead_findings": None,
            "compiler_diagnostics": None,
            "errors": [],
            "repair": {"packet": None, "output": None, "attempts": []},
            "adjudication": {"packet": None, "output": None, "status": "not_run"},
            "final_draft": None,
            "usage": {"records": [], "summary": {"groups": [], "totals": {}}},
        }

    def record_plan(self, plan: Any, *, status: str = "completed", model: str | None = None) -> None:
        self._state["plan"] = {
            "status": status,
            "model": model,
            "recorded_at": _now(),
            "content": _safe(plan),
        }
        self._touch()

    def record_delegation(
        self,
        *,
        role: str,
        shard: str | None,
        task: Any,
        status: str,
        model: str | None = None,
        delegation_id: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        child_memo: Any = None,
    ) -> str:
        identifier = delegation_id or f"delegation_{len(self._state['delegations'])}"
        record = {
            "delegation_id": identifier,
            "role": role,
            "shard": shard,
            "task": _safe(task),
            "status": status,
            "model": model,
            "started_at": started_at or _now(),
            "finished_at": finished_at,
            "child_memo": _safe(child_memo) if child_memo is not None else None,
        }
        existing = next(
            (item for item in self._state["delegations"] if item["delegation_id"] == identifier),
            None,
        )
        if existing is None:
            self._state["delegations"].append(record)
        else:
            existing.update(record)
        self._touch()
        return identifier

    def record_tool_activity(
        self,
        *,
        tool: str,
        status: str,
        role: str | None = None,
        shard: str | None = None,
        model: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        self._state["tool_activity"].append({
            "tool": tool,
            "status": status,
            "role": role,
            "shard": shard,
            "model": model,
            "started_at": started_at or _now(),
            "finished_at": finished_at,
            "metadata": _safe(metadata or {}),
        })
        self._touch()

    def record_corpus_read(
        self,
        observation: Mapping[str, Any],
        summary: Mapping[str, Any],
    ) -> None:
        """Persist host-observed corpus text counts, not envelope characters."""

        metric = dict(summary)
        observations = list(self._state.get("corpus_read", {}).get("observations", ()))
        if observation:
            observations.append(_safe(observation))
            self._state["tool_activity"].append({
                "tool": observation.get("tool"),
                "kind": "corpus_read",
                "status": "observed",
                "role": observation.get("actor_role"),
                "shard": observation.get("shard"),
                "metadata": {
                    "returned_corpus_text_tokens": observation.get(
                        "returned_corpus_text_tokens", 0,
                    ),
                    "text_item_count": observation.get("text_item_count", 0),
                    "truncated": bool(observation.get("truncated")),
                    "ownership_tokens": observation.get("ownership_tokens", {}),
                },
            })
        metric["observations"] = observations
        self._state["corpus_read"] = _safe(metric)
        self._touch()
        if self.output_path is not None:
            self.persist()

    def record_message_history(
        self,
        messages: Any,
        *,
        role: str | None = None,
        shard: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Extract and append planning and tool metadata from Pydantic messages."""

        trace = extract_message_history_trace(messages)
        annotations = {"role": role, "shard": shard, "model": model}
        planning = [{**item, **annotations} for item in trace["planning"]]
        activity = [{**item, **annotations} for item in trace["tool_activity"]]
        self._state["planning_events"].extend(planning)
        self._state["tool_activity"].extend(activity)
        self._touch()
        return {"planning": planning, "tool_activity": activity}

    def record_findings(self, findings: Any) -> None:
        self._state["lead_findings"] = _safe(findings)
        self._touch()

    def record_compiler_diagnostics(self, diagnostics: Any) -> None:
        self._state["compiler_diagnostics"] = _safe(diagnostics)
        self._touch()

    def record_repair(
        self,
        *,
        packet: Any = _MISSING,
        output: Any = _MISSING,
        attempt: int | None = None,
        batch_id: str | None = None,
        batch_index: int | None = None,
        batch_count: int | None = None,
    ) -> None:
        if packet is not _MISSING:
            self._state["repair"]["packet"] = _safe(packet)
        if output is not _MISSING:
            self._state["repair"]["output"] = _safe(output)
        if attempt is not None:
            existing = next((
                item for item in self._state["repair"]["attempts"]
                if item["attempt"] == attempt and item.get("batch_id") == batch_id
            ), None)
            if existing is None:
                existing = {
                    "attempt": attempt, "batch_id": batch_id,
                    "batch_index": batch_index, "batch_count": batch_count,
                    "recorded_at": _now(),
                    "packet": None, "output": None,
                }
                self._state["repair"]["attempts"].append(existing)
            else:
                if batch_index is not None:
                    existing["batch_index"] = batch_index
                if batch_count is not None:
                    existing["batch_count"] = batch_count
            if packet is not _MISSING:
                existing["packet"] = _safe(packet)
            if output is not _MISSING:
                existing["output"] = _safe(output)
        self._touch()

    def record_adjudication(
        self,
        *,
        packet: Any = _MISSING,
        output: Any = _MISSING,
        status: str | None = None,
    ) -> None:
        """Record the one-batch event-edge adjudication separately from repair."""

        if packet is not _MISSING:
            self._state["adjudication"]["packet"] = _safe(packet)
        if output is not _MISSING:
            self._state["adjudication"]["output"] = _safe(output)
        if status is not None:
            self._state["adjudication"]["status"] = str(status)
        self._touch()

    def record_final_draft(self, draft: Any) -> None:
        self._state["final_draft"] = _safe(draft)
        self._touch()

    def record_error(
        self,
        error: BaseException | Any,
        *,
        stage: str,
        role: str | None = None,
        shard: str | None = None,
    ) -> None:
        """Record a bounded, redacted failure without retaining exception objects."""

        self._state["errors"].append({
            "stage": str(stage),
            "role": role,
            "shard": shard,
            "error_type": type(error).__name__,
            "message": _redact_error_message(str(error)),
            "recorded_at": _now(),
        })
        self._touch()

    def record_usage(self, record: UsageRecord | Mapping[str, Any], **overrides: Any) -> None:
        candidate = record.to_dict() if isinstance(record, UsageRecord) else dict(record)
        candidate.update(overrides)
        normalized = normalize_usage(candidate)
        self._state["usage"]["records"].append(normalized.to_dict())
        self._state["usage"]["summary"] = self._summarize_usage()
        self._touch()

    def snapshot(self) -> dict[str, Any]:
        """Return a detached, JSON-safe snapshot suitable for inspection."""

        return _safe(self._state)

    def persist(self, output_path: str | os.PathLike[str] | None = None) -> Path:
        """Atomically replace the configured ledger path with UTF-8 JSON."""

        path = Path(output_path) if output_path is not None else self.output_path
        if path is None:
            raise ValueError("an output_path is required to persist a trace ledger")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.snapshot(), ensure_ascii=False, indent=2) + "\n"
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.",
                suffix=".tmp", delete=False,
            ) as handle:
                temporary_path = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path is not None and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        self.output_path = path
        return path

    def _summarize_usage(self) -> dict[str, Any]:
        return summarize_usage(self._state["usage"]["records"])

    def _touch(self) -> None:
        self._state["updated_at"] = _now()


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = [
    "ContextResearchTraceCollector",
    "UsageRecord",
    "extract_message_history_trace",
    "usage_record_from_run_usage",
]
