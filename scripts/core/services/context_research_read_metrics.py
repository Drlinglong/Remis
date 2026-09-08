"""Deterministic corpus-read accounting for Context Research runs.

Only text returned by the registered corpus tools is observed here.  Provider
prompt usage and serialized tool envelopes deliberately remain outside this
metric's boundary.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Any


TOKENIZER_LIBRARY = "tiktoken"
TOKENIZER_ENCODING = "o200k_base"
TOKENIZER_VERSION = "0.13.0"
METRIC_SCHEMA_VERSION = "corpus-read-amplification-v1"
READ_TOOLS = frozenset({
    "read_units", "search_units", "read_investigation_shards",
    "read_corpus", "search_corpus",
})


@dataclass(frozen=True)
class CorpusReadObservation:
    """One successful model-facing corpus-tool return."""

    actor_role: str
    tool: str
    returned_corpus_text_tokens: int
    text_item_count: int
    source_item_ids: tuple[str, ...]
    source_item_tokens: Mapping[str, int]
    ownership_tokens: Mapping[str, int]
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_role": self.actor_role,
            "tool": self.tool,
            "returned_corpus_text_tokens": self.returned_corpus_text_tokens,
            "text_item_count": self.text_item_count,
            "source_item_ids": list(self.source_item_ids),
            "source_item_tokens": dict(self.source_item_tokens),
            "ownership_tokens": dict(self.ownership_tokens),
            "truncated": self.truncated,
        }


class CorpusReadMeter:
    """Count returned corpus text, including repeated reads."""

    def __init__(
        self,
        source_items: Sequence[Any],
        *,
        on_observation: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
    ) -> None:
        self._on_observation = on_observation
        self._observations: list[CorpusReadObservation] = []
        self._by_actor: Counter[str] = Counter()
        self._by_tool: Counter[str] = Counter()
        self._by_role_tool: Counter[str] = Counter()
        self._ownership_tokens: Counter[str] = Counter()
        self._source_tokens: dict[str, int] = {}
        self._unobserved_calls = 0
        self._available = True
        self._tokenizer_error: str | None = None
        try:
            import tiktoken

            self._encoder = tiktoken.get_encoding(TOKENIZER_ENCODING)
        except Exception as error:  # pragma: no cover - environment dependent
            self._encoder = None
            self._available = False
            self._tokenizer_error = type(error).__name__ + ": " + str(error)
        snapshot_parts: list[dict[str, str]] = []
        for item in source_items:
            source_id = _field(item, "source_item_id", "id")
            if source_id:
                text = _text(item)
                self._source_tokens[source_id] = self._count(text)
                snapshot_parts.append({"source_item_id": source_id, "text": text})
        self._denominator_tokens = sum(self._source_tokens.values())
        self._source_snapshot_hash = hashlib.sha256(
            json.dumps(snapshot_parts, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @property
    def available(self) -> bool:
        return self._available

    def set_observation_sink(
        self,
        sink: Callable[[dict[str, Any], dict[str, Any]], None] | None,
    ) -> None:
        """Attach or replace the persistence callback after trace creation."""

        self._on_observation = sink

    def observe(
        self,
        tool: str,
        result: Mapping[str, Any],
        *,
        actor_role: str,
        source_id_resolver: Callable[[str], str] | None = None,
    ) -> dict[str, Any]:
        """Record one tool result using explicit corpus response paths."""

        if tool not in READ_TOOLS:
            return CorpusReadObservation(
                actor_role=actor_role,
                tool=tool,
                returned_corpus_text_tokens=0,
                text_item_count=0,
                source_item_ids=(),
                source_item_tokens={},
                ownership_tokens={},
                truncated=False,
            ).to_dict()
        observation = self._observation(tool, result, actor_role, source_id_resolver)
        self._observations.append(observation)
        self._by_actor[observation.actor_role] += observation.returned_corpus_text_tokens
        self._by_tool[observation.tool] += observation.returned_corpus_text_tokens
        self._by_role_tool[
            f"{observation.actor_role}:{observation.tool}"
        ] += observation.returned_corpus_text_tokens
        self._ownership_tokens.update(observation.ownership_tokens)
        rendered = observation.to_dict()
        summary = self.snapshot()
        if self._on_observation is not None:
            self._on_observation(rendered, summary)
        return rendered

    def record_failure(self, tool: str, *, actor_role: str, error: BaseException) -> None:
        self._available = False
        self._unobserved_calls += 1
        self._tokenizer_error = f"tool_failure:{tool}:{type(error).__name__}"
        if self._on_observation is not None:
            self._on_observation(
                {
                    "actor_role": actor_role,
                    "tool": tool,
                    "status": "failed",
                    "returned_corpus_text_tokens": 0,
                    "text_item_count": 0,
                    "ownership_tokens": {},
                    "truncated": False,
                },
                self.snapshot(),
            )

    def snapshot(self) -> dict[str, Any]:
        numerator = sum(item.returned_corpus_text_tokens for item in self._observations)
        first_read = self._first_read_tokens()
        per_call = sorted(item.returned_corpus_text_tokens for item in self._observations)
        denominator = self._denominator_tokens
        return {
            "schema_version": METRIC_SCHEMA_VERSION,
            "metric_name": "Corpus Read Amplification",
            "definition": (
                "sum of corpus text tokens returned by corpus tools per eligible "
                "corpus text tokens"
            ),
            "numerator_tokens": numerator,
            "denominator_tokens": denominator,
            "eligible_source_item_count": len(self._source_tokens),
            "source_snapshot_hash": self._source_snapshot_hash,
            "value": (
                numerator / denominator
                if self._available and denominator > 0 else None
            ),
            "tokenizer": {
                "library": TOKENIZER_LIBRARY,
                "encoding": TOKENIZER_ENCODING,
                "version": TOKENIZER_VERSION,
                "available": self._available,
                "error": self._tokenizer_error,
            },
            "by_actor": dict(self._by_actor),
            "by_tool": dict(self._by_tool),
            "by_role_tool": dict(self._by_role_tool),
            "by_ownership": dict(self._ownership_tokens),
            "unique_coverage_tokens": first_read,
            "unique_coverage": first_read / denominator if denominator else 0.0,
            "reread_tokens": max(0, numerator - first_read),
            "call_count": len(self._observations),
            "p50_tokens_per_call": _percentile(per_call, 0.50),
            "p95_tokens_per_call": _percentile(per_call, 0.95),
            "max_tokens_per_call": max(per_call, default=0),
            "complete": self._available,
            "unobserved_calls": self._unobserved_calls,
            "observation_count": len(self._observations),
            "backfill_status": "observed" if self._available else "incomplete",
        }

    def _observation(
        self,
        tool: str,
        result: Mapping[str, Any],
        actor_role: str,
        source_id_resolver: Callable[[str], str] | None,
    ) -> CorpusReadObservation:
        texts: list[tuple[str, str, str | None]] = []
        truncated = bool(result.get("truncated"))
        if tool in {"read_corpus", "search_corpus"}:
            texts = [
                (str(item.get("source_item_id", "")), str(item.get("text", "")), item.get("ownership"))
                for item in result.get("items", ())
                if isinstance(item, Mapping) and isinstance(item.get("text"), str)
            ]
            truncated = truncated or any(bool(item.get("text_truncated")) for item in result.get("items", ()) if isinstance(item, Mapping))
        elif tool in {"read_units", "search_units"}:
            for unit in result.get("units", ()):
                if not isinstance(unit, Mapping):
                    continue
                truncated = truncated or bool(unit.get("truncated"))
                for entry in unit.get("entries", ()):
                    if isinstance(entry, Mapping) and isinstance(entry.get("text"), str):
                        texts.append((str(entry.get("source_item_id", "")), str(entry["text"]), entry.get("ownership") or unit.get("ownership")))
        elif tool == "read_investigation_shards":
            for shard in result.get("shards", ()):
                if not isinstance(shard, Mapping):
                    continue
                truncated = truncated or bool(shard.get("truncated"))
                for unit in shard.get("units", ()):
                    if not isinstance(unit, Mapping):
                        continue
                    for entry in unit.get("entries", ()):
                        if isinstance(entry, Mapping) and isinstance(entry.get("text"), str):
                            texts.append((str(entry.get("source_item_id", "")), str(entry["text"]), entry.get("ownership") or unit.get("ownership")))
        ownership = Counter()
        source_item_tokens = Counter()
        source_ids: list[str] = []
        tokens = 0
        for source_id, text, item_ownership in texts:
            count = self._count(text)
            tokens += count
            ownership[str(item_ownership or "unscoped")] += count
            if source_id:
                canonical_id = source_id_resolver(source_id) if source_id_resolver is not None else source_id
                source_ids.append(canonical_id)
                source_item_tokens[canonical_id] += count
        return CorpusReadObservation(
            actor_role=actor_role,
            tool=tool,
            returned_corpus_text_tokens=tokens,
            text_item_count=len(texts),
            source_item_ids=tuple(dict.fromkeys(source_ids)),
            source_item_tokens=source_item_tokens,
            ownership_tokens=ownership,
            truncated=truncated,
        )

    def _first_read_tokens(self) -> int:
        seen: set[str] = set()
        total = 0
        for observation in self._observations:
            for source_id in observation.source_item_ids:
                if source_id not in seen:
                    seen.add(source_id)
                    total += observation.source_item_tokens.get(source_id, 0)
        return total

    def _count(self, text: str) -> int:
        return len(self._encoder.encode(text)) if self._encoder is not None else 0


def _field(value: Any, *names: str) -> str:
    for name in names:
        candidate = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
        if candidate:
            return str(candidate)
    return ""


def _text(value: Any) -> str:
    return str(_field(value, "source_text", "text"))


def _percentile(values: Sequence[int], quantile: float) -> int:
    if not values:
        return 0
    index = min(len(values) - 1, max(0, int((len(values) - 1) * quantile + 0.999999)))
    return int(values[index])


__all__ = [
    "CorpusReadMeter", "CorpusReadObservation", "METRIC_SCHEMA_VERSION",
    "TOKENIZER_ENCODING", "TOKENIZER_LIBRARY", "TOKENIZER_VERSION",
]
