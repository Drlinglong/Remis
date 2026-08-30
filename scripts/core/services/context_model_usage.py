"""Thread-safe model-call telemetry for one context-analysis workflow."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import threading
from typing import Any


class ContextModelUsageLedger:
    """Collect provider-authored usage without inventing missing cost data."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: list[dict[str, Any]] = []
        self._reasoning_profiles: list[str] = []

    def capture(self, handler: Any, phase: str) -> None:
        consume = getattr(handler, "consume_model_call_records", None)
        records = consume() if callable(consume) else []
        profile = self._reasoning_profile(handler)
        with self._lock:
            if profile and profile not in self._reasoning_profiles:
                self._reasoning_profiles.append(profile)
            self._records.extend({**record, "phase": phase} for record in records)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            records = deepcopy(self._records)
            profiles = list(self._reasoning_profiles)
        by_phase: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"call_count": 0, "input_tokens": 0, "output_tokens": 0,
                     "reasoning_tokens": 0, "total_tokens": 0, "cost": 0.0,
                     "usage_missing_calls": 0, "cost_missing_calls": 0}
        )
        for record in records:
            bucket = by_phase[str(record.get("phase") or "unknown")]
            bucket["call_count"] += 1
            if not record.get("usage_reported"):
                bucket["usage_missing_calls"] += 1
            if record.get("cost") is None:
                bucket["cost_missing_calls"] += 1
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
                bucket[key] += int(record.get(key) or 0)
            bucket["cost"] += float(record.get("cost") or 0.0)
        totals = {
            key: sum(int(item[key]) for item in by_phase.values())
            for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens")
        }
        missing_usage = sum(int(item["usage_missing_calls"]) for item in by_phase.values())
        missing_cost = sum(int(item["cost_missing_calls"]) for item in by_phase.values())
        call_count = len(records)
        return {
            "call_count": call_count,
            "reasoning_profile": ", ".join(profiles) if profiles else "not_reported",
            "token_usage": totals if call_count and missing_usage < call_count else None,
            "cost": (
                {"amount": round(sum(float(item["cost"]) for item in by_phase.values()), 8),
                 "currency": "USD", "complete": missing_cost == 0}
                if call_count and missing_cost < call_count else None
            ),
            "usage_note": self._usage_note(call_count, missing_usage, missing_cost),
            "by_phase": dict(by_phase),
        }

    @staticmethod
    def _usage_note(call_count: int, missing_usage: int, missing_cost: int) -> str:
        if not call_count:
            return "Provider adapters captured no model response metadata."
        if not missing_usage and not missing_cost:
            return "All token and cost values were reported by provider responses."
        return (
            f"Provider responses omitted usage for {missing_usage}/{call_count} calls "
            f"and cost for {missing_cost}/{call_count} calls; missing values were not estimated."
        )

    @staticmethod
    def _reasoning_profile(handler: Any) -> str | None:
        get_config = getattr(handler, "get_provider_config", None)
        if not callable(get_config):
            return None
        config = get_config()
        if config.get("reasoning_effort"):
            return f"reasoning_effort={config['reasoning_effort']}"
        if config.get("thinking_budget") is not None:
            return f"thinking_budget={config['thinking_budget']}"
        if config.get("enable_thinking") is not None:
            return f"thinking={'enabled' if config['enable_thinking'] else 'disabled'}"
        return None
