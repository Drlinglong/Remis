"""Bounded, read-only corpus tools for the developer research harness.

The research proof of concept is deliberately given a small object-capability
surface.  It never receives a project path, a filesystem handle, a web client,
or a writer.  A Remis corpus adapter only has to implement ``iter_source_items``
and may therefore be backed by an in-memory fixture in tests or by an existing
Remis repository in a developer-only integration.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit


DEFAULT_MAX_ITEMS = 12
DEFAULT_MAX_ITEM_CHARS = 1200
DEFAULT_MAX_TOTAL_CHARS = 8000
MAX_ALLOWED_ITEMS = 64
MAX_ALLOWED_ITEM_CHARS = 4000
MAX_ALLOWED_TOTAL_CHARS = 24000
SENSITIVE_METADATA_TOKENS = (
    "authorization", "credential", "api_key", "secret", "token",
)


@dataclass(frozen=True)
class CorpusSourceItem:
    """A source card that is safe to expose to an analysis agent.

    ``source_item_id`` is the stable evidence identity.  Paths and keys are
    descriptive metadata only; this object intentionally contains no methods
    that can open or mutate a file.
    """

    source_item_id: str
    text: str
    path: str = ""
    key: str = ""
    metadata: Mapping[str, Any] | None = None


class CorpusReader(Protocol):
    """Minimal read-only port implemented by a Remis corpus repository."""

    def iter_source_items(
        self,
        project_id: str,
        source_item_ids: Sequence[str] | None = None,
    ) -> Iterable[CorpusSourceItem | Mapping[str, Any]]: ...


@dataclass(frozen=True)
class CorpusToolLimits:
    """Hard output budgets applied independently to every corpus tool call."""

    max_items: int = DEFAULT_MAX_ITEMS
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS

    def __post_init__(self) -> None:
        if not 1 <= self.max_items <= MAX_ALLOWED_ITEMS:
            raise ValueError(f"max_items must be between 1 and {MAX_ALLOWED_ITEMS}")
        if not 1 <= self.max_item_chars <= MAX_ALLOWED_ITEM_CHARS:
            raise ValueError(
                f"max_item_chars must be between 1 and {MAX_ALLOWED_ITEM_CHARS}"
            )
        if not 1 <= self.max_total_chars <= MAX_ALLOWED_TOTAL_CHARS:
            raise ValueError(
                f"max_total_chars must be between 1 and {MAX_ALLOWED_TOTAL_CHARS}"
            )


def _bounded_text(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def _as_item(value: CorpusSourceItem | Mapping[str, Any]) -> CorpusSourceItem:
    if isinstance(value, CorpusSourceItem):
        return value
    source_item_id = str(value.get("source_item_id") or value.get("id") or "").strip()
    return CorpusSourceItem(
        source_item_id=source_item_id,
        text=str(value.get("text") or value.get("source_text") or ""),
        path=str(value.get("path") or ""),
        key=str(value.get("key") or value.get("item_key") or ""),
        metadata=value.get("metadata") if isinstance(value.get("metadata"), Mapping) else None,
    )


def _safe_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            _bounded_text(key, 80): _safe_metadata(item)
            for key, item in list(value.items())[:12]
            if not any(token in str(key).casefold() for token in SENSITIVE_METADATA_TOKENS)
        }
    if isinstance(value, (list, tuple)):
        return [_safe_metadata(item) for item in value[:12]]
    return _bounded_text(value, 240)


class ReadOnlyRemisCorpusTools:
    """Safe, deterministic corpus tools used by all harness agents.

    The public methods return JSON-shaped values so they can be registered as
    PydanticAI tools without leaking repository objects.  Unknown IDs are
    omitted, and every returned record is bounded by ``CorpusToolLimits``.
    """

    def __init__(self, reader: CorpusReader, limits: CorpusToolLimits | None = None) -> None:
        self._reader = reader
        self.limits = limits or CorpusToolLimits()

    def _items(self, project_id: str, source_item_ids: Sequence[str] | None = None) -> Iterator[CorpusSourceItem]:
        wanted = {str(item).strip() for item in source_item_ids or () if str(item).strip()}
        for raw in self._reader.iter_source_items(project_id, source_item_ids):
            item = _as_item(raw)
            if item.source_item_id and (not wanted or item.source_item_id in wanted):
                yield item

    def _record(self, item: CorpusSourceItem, *, include_text: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "source_item_id": item.source_item_id,
            "path": _bounded_text(item.path, 240),
            "key": _bounded_text(item.key, 240),
        }
        if include_text:
            record["text"] = _bounded_text(item.text, self.limits.max_item_chars)
        if item.metadata:
            record["metadata"] = _safe_metadata(item.metadata)
        return record

    def _bounded_records(self, items: Iterable[CorpusSourceItem], *, include_text: bool = True) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        used = 0
        for item in items:
            if len(records) >= self.limits.max_items:
                break
            record = self._record(item, include_text=include_text)
            cost = sum(len(str(value)) for value in record.values())
            if records and used + cost > self.limits.max_total_chars:
                break
            if not records and cost > self.limits.max_total_chars:
                # Keep identity fields intact and trim the optional payload to
                # the remaining total budget.  A tool call never exceeds its
                # aggregate character limit, even with a very small fixture
                # budget.
                identity_cost = sum(
                    len(str(value)) for key, value in record.items() if key != "text"
                )
                remaining = max(0, self.limits.max_total_chars - identity_cost)
                if include_text and "text" in record:
                    record["text"] = _bounded_text(record["text"], remaining)
                record.pop("metadata", None)
                cost = sum(len(str(value)) for value in record.values())
                if cost > self.limits.max_total_chars:
                    break
            records.append(record)
            used += cost
        return records

    def list_source_items(
        self,
        project_id: str,
        source_item_ids: Sequence[str] | None = None,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List bounded source cards without returning their complete text."""

        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        items = list(self._items(project_id, source_item_ids))
        records = self._bounded_records(items[offset:], include_text=False)
        has_more = offset + len(records) < len(items)
        return {
            "items": records,
            "count": len(records),
            "returned_count": len(records),
            "offset": offset,
            "next_offset": offset + len(records) if has_more else None,
            "has_more": has_more,
            "read_only": True,
        }

    def read_source_items(self, project_id: str, source_item_ids: Sequence[str]) -> dict[str, Any]:
        """Read only explicitly named source cards, retaining evidence IDs."""

        requested = list(dict.fromkeys(
            str(item).strip() for item in source_item_ids if str(item).strip()
        ))
        available = list(self._items(project_id, requested))
        records = self._bounded_records(available)
        available_ids = {item.source_item_id for item in available}
        returned = {str(item["source_item_id"]) for item in records}
        return {
            "items": records,
            "count": len(records),
            "requested_source_item_ids": requested[: self.limits.max_items],
            "missing_source_item_ids": [
                item for item in requested if item not in available_ids
            ][: self.limits.max_items],
            "truncated_source_item_ids": [
                item for item in requested
                if item in available_ids and item not in returned
            ][: self.limits.max_items],
            "read_only": True,
        }

    def search_source_items(
        self,
        project_id: str,
        query: str,
        source_item_ids: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        """Perform deterministic local substring search over supplied corpus data."""

        normalized = _bounded_text(query, 400).strip().casefold()
        if not normalized:
            return {"items": [], "count": 0, "query": "", "read_only": True}
        matches = (
            item for item in self._items(project_id, source_item_ids)
            if normalized in f"{item.key} {item.text}".casefold()
        )
        all_matches = list(matches)
        result = self._bounded_records(all_matches)
        has_more = len(result) < len(all_matches)
        return {
            "items": result,
            "count": len(result),
            "returned_count": len(result),
            "has_more": has_more,
            "query": normalized,
            "read_only": True,
        }

    # Short names make registration with external harness implementations easy.
    list = list_source_items
    read = read_source_items
    search = search_source_items


class BoundCorpusTools:
    """Request-scoped view; model tool arguments cannot escape the snapshot."""

    def __init__(
        self,
        tools: ReadOnlyRemisCorpusTools,
        project_id: str,
        source_item_ids: Sequence[str] | None,
        source_items: Sequence[Any] | None = None,
    ) -> None:
        self._tools = tools
        self._project_id = project_id
        self._source_item_ids = tuple(dict.fromkeys(str(item) for item in source_item_ids or () if str(item).strip()))
        if not self._source_item_ids:
            raise ValueError("BoundCorpusTools requires a non-empty source snapshot")
        bounded_items = tuple(
            item for item in source_items or ()
            if str(getattr(item, "source_item_id", "")) in self._source_item_ids
        )
        self._local_units = ContextLocalUnitBuilder.build(bounded_items)
        self._local_unit_by_id = {unit.unit_id: unit for unit in self._local_units}

    @property
    def limits(self) -> CorpusToolLimits:
        return self._tools.limits

    def list_source_items(self, offset: int = 0) -> dict[str, Any]:
        return self._tools.list_source_items(
            self._project_id, self._source_item_ids or None, offset=offset,
        )

    def read_source_items(self, source_item_ids: Sequence[str] | None = None) -> dict[str, Any]:
        requested = self._source_item_ids
        rejected: tuple[str, ...] = ()
        if source_item_ids is not None:
            allowed = set(self._source_item_ids)
            normalized = tuple(dict.fromkeys(
                str(item).strip() for item in source_item_ids if str(item).strip()
            ))
            requested = tuple(item for item in normalized if item in allowed)
            rejected = tuple(item for item in normalized if item not in allowed)
        result = self._tools.read_source_items(self._project_id, requested)
        result["rejected_source_item_ids"] = list(rejected)[: self.limits.max_items]
        return result

    def search_source_items(self, query: str) -> dict[str, Any]:
        return self._tools.search_source_items(
            self._project_id, query, self._source_item_ids or None,
        )

    def list_local_units(self, offset: int = 0) -> dict[str, Any]:
        """List deterministic key families without source text."""

        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        units = self._local_units[offset: offset + self.limits.max_items]
        next_offset = offset + len(units)
        return {
            "units": [self._unit_record(unit, include_text=False) for unit in units],
            "count": len(units),
            "offset": offset,
            "next_offset": next_offset if next_offset < len(self._local_units) else None,
            "has_more": next_offset < len(self._local_units),
            "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def read_local_units(self, local_unit_ids: Sequence[str]) -> dict[str, Any]:
        """Read complete title/description/option families for named units."""

        requested = tuple(dict.fromkeys(
            str(item).strip() for item in local_unit_ids if str(item).strip()
        ))[: self.limits.max_items]
        accepted = tuple(unit_id for unit_id in requested if unit_id in self._local_unit_by_id)
        return {
            "units": [
                self._unit_record(self._local_unit_by_id[unit_id], include_text=True)
                for unit_id in accepted
            ],
            "count": len(accepted),
            "requested_local_unit_ids": list(requested),
            "rejected_local_unit_ids": [
                unit_id for unit_id in requested if unit_id not in self._local_unit_by_id
            ],
            "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def search_local_units(self, query: str) -> dict[str, Any]:
        """Search key-family units while preserving all sibling entries."""

        normalized = _bounded_text(query, 400).strip().casefold()
        if not normalized:
            return {"units": [], "count": 0, "query": "", "read_only": True}
        matches = [unit for unit in self._local_units if normalized in self._unit_text(unit)]
        limited = matches[: self.limits.max_items]
        return {
            "units": [self._unit_record(unit, include_text=True) for unit in limited],
            "count": len(limited),
            "has_more": len(limited) < len(matches),
            "query": normalized,
            "read_only": True,
            "structure_source": "deterministic_key_family_hint",
        }

    def _unit_record(self, unit: LocalTextUnit, *, include_text: bool) -> dict[str, Any]:
        entries = []
        used = 0
        for item in unit.items:
            entry = {
                "source_item_id": str(item.source_item_id),
                "key": str(item.item_key or ""),
                "source_order": item.source_order,
            }
            if include_text:
                remaining = max(0, self.limits.max_total_chars - used)
                entry["text"] = _bounded_text(item.source_text, min(
                    self.limits.max_item_chars, remaining,
                ))
            used += sum(len(str(value)) for value in entry.values())
            if used > self.limits.max_total_chars:
                break
            entries.append(entry)
        return {
            "local_unit_id": unit.unit_id,
            "derived_unit_key": unit.unit_key.split("::", 1)[-1],
            "item_keys": [str(item.item_key or "") for item in unit.items],
            "entries": entries,
        }

    @staticmethod
    def _unit_text(unit: LocalTextUnit) -> str:
        return " ".join(
            f"{item.item_key or ''} {item.source_text}" for item in unit.items
        ).casefold()


class InMemoryCorpus:
    """Tiny corpus adapter intended for tests and local harness experiments."""

    def __init__(self, items: Iterable[CorpusSourceItem | Mapping[str, Any]]) -> None:
        self.items = tuple(_as_item(item) for item in items)

    def iter_source_items(
        self,
        project_id: str,
        source_item_ids: Sequence[str] | None = None,
    ) -> Iterable[CorpusSourceItem]:
        del project_id  # Project partitioning belongs to the injected fixture.
        wanted = set(source_item_ids or ())
        return (
            item for item in self.items
            if not wanted or item.source_item_id in wanted
        )


# Explicit alias used by callers that prefer the shorter name.
RemisCorpusTools = ReadOnlyRemisCorpusTools


__all__ = [
    "CorpusReader",
    "CorpusSourceItem",
    "InMemoryCorpus",
    "ReadOnlyRemisCorpusTools",
    "RemisCorpusTools",
    "BoundCorpusTools",
    "CorpusToolLimits",
]
