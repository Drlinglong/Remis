"""Request-safe corpus normalization and bounded source-item tools."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol


DEFAULT_MAX_ITEMS = 12
DEFAULT_MAX_ITEM_CHARS = 1200
DEFAULT_MAX_TOTAL_CHARS = 8000
MAX_ALLOWED_ITEMS = 64
MAX_ALLOWED_ITEM_CHARS = 4000
MAX_ALLOWED_TOTAL_CHARS = 24000
SENSITIVE_METADATA_TOKENS = ("authorization", "credential", "api_key", "secret", "token")


@dataclass(frozen=True)
class CorpusSourceItem:
    """Canonical read-only source item used by corpus tools and local-unit building."""

    source_item_id: str
    text: str
    path: str = ""
    key: str = ""
    metadata: Mapping[str, Any] | None = None

    @property
    def source_text(self) -> str:
        return self.text

    @property
    def relative_path(self) -> str:
        return self.path

    @property
    def item_key(self) -> str:
        return self.key

    @property
    def source_order(self) -> int | None:
        value = self.metadata.get("source_order") if self.metadata else None
        return value if isinstance(value, int) and not isinstance(value, bool) else None


class CorpusReader(Protocol):
    def iter_source_items(
        self, project_id: str, source_item_ids: Sequence[str] | None = None,
    ) -> Iterable[CorpusSourceItem | Mapping[str, Any]]: ...


@dataclass(frozen=True)
class CorpusToolLimits:
    max_items: int = DEFAULT_MAX_ITEMS
    max_item_chars: int = DEFAULT_MAX_ITEM_CHARS
    max_total_chars: int = DEFAULT_MAX_TOTAL_CHARS

    def __post_init__(self) -> None:
        if not 1 <= self.max_items <= MAX_ALLOWED_ITEMS:
            raise ValueError(f"max_items must be between 1 and {MAX_ALLOWED_ITEMS}")
        if not 1 <= self.max_item_chars <= MAX_ALLOWED_ITEM_CHARS:
            raise ValueError(f"max_item_chars must be between 1 and {MAX_ALLOWED_ITEM_CHARS}")
        if not 1 <= self.max_total_chars <= MAX_ALLOWED_TOTAL_CHARS:
            raise ValueError(f"max_total_chars must be between 1 and {MAX_ALLOWED_TOTAL_CHARS}")


def bounded_text(value: Any, limit: int) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: max(0, limit - 1)] + "…"


def normalize_source_item(value: CorpusSourceItem | Mapping[str, Any] | Any) -> CorpusSourceItem:
    """Normalize either a repository record or request SourceItem.

    The aliases are intentional: request snapshots use ``relative_path`` /
    ``item_key`` / ``source_text``, while repository readers use ``path`` /
    ``key`` / ``text``.  Keeping this conversion here lets ID-only requests
    build the same local-unit graph as requests carrying materialized items.
    """

    if isinstance(value, CorpusSourceItem):
        return value
    get = value.get if isinstance(value, Mapping) else lambda key: getattr(value, key, None)
    source_id = str(get("source_item_id") or get("id") or "").strip()
    metadata = get("metadata") if isinstance(get("metadata"), Mapping) else {}
    source_order = get("source_order")
    if isinstance(source_order, int) and not isinstance(source_order, bool):
        metadata = {**metadata, "source_order": source_order}
    return CorpusSourceItem(
        source_item_id=source_id,
        text=str(get("text") or get("source_text") or ""),
        path=str(get("path") or get("relative_path") or ""),
        key=str(get("key") or get("item_key") or ""),
        metadata=metadata or None,
    )


def safe_metadata(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            bounded_text(key, 80): safe_metadata(item)
            for key, item in list(value.items())[:12]
            if not any(token in str(key).casefold() for token in SENSITIVE_METADATA_TOKENS)
        }
    if isinstance(value, (list, tuple)):
        return [safe_metadata(item) for item in value[:12]]
    return bounded_text(value, 240)


class ReadOnlyRemisCorpusTools:
    """Bounded, source-only tools backed by an injected reader."""

    def __init__(self, reader: CorpusReader, limits: CorpusToolLimits | None = None) -> None:
        self._reader = reader
        self.limits = limits or CorpusToolLimits()

    def _items(self, project_id: str, source_item_ids: Sequence[str] | None = None) -> Iterator[CorpusSourceItem]:
        wanted = {str(item).strip() for item in source_item_ids or () if str(item).strip()}
        for raw in self._reader.iter_source_items(project_id, source_item_ids):
            item = normalize_source_item(raw)
            if item.source_item_id and (not wanted or item.source_item_id in wanted):
                yield item

    def _record(self, item: CorpusSourceItem, *, include_text: bool = True) -> dict[str, Any]:
        record: dict[str, Any] = {
            "source_item_id": item.source_item_id,
            "path": bounded_text(item.path, 240),
            "key": bounded_text(item.key, 240),
        }
        if include_text:
            record["text"] = bounded_text(item.text, self.limits.max_item_chars)
            record["text_truncated"] = len(item.text) > self.limits.max_item_chars
        if item.metadata:
            record["metadata"] = safe_metadata(item.metadata)
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
                record.pop("metadata", None)
                if "text" in record:
                    identity_cost = sum(len(str(value)) for key, value in record.items() if key != "text")
                    record["text"] = bounded_text(record["text"], max(0, self.limits.max_total_chars - identity_cost))
                    record["text_truncated"] = True
                cost = sum(len(str(value)) for value in record.values())
                if cost > self.limits.max_total_chars:
                    break
            records.append(record)
            used += cost
        return records

    def list_source_items(self, project_id: str, source_item_ids: Sequence[str] | None = None, offset: int = 0) -> dict[str, Any]:
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        items = list(self._items(project_id, source_item_ids))
        records = self._bounded_records(items[offset:], include_text=False)
        next_offset = offset + len(records)
        return {
            "items": records, "count": len(records), "returned_count": len(records),
            "offset": offset, "next_offset": next_offset if next_offset < len(items) else None,
            "has_more": next_offset < len(items), "read_only": True,
        }

    def read_source_items(self, project_id: str, source_item_ids: Sequence[str]) -> dict[str, Any]:
        requested = tuple(dict.fromkeys(str(item).strip() for item in source_item_ids if str(item).strip()))
        available = list(self._items(project_id, requested))
        records = self._bounded_records(available)
        available_ids = {item.source_item_id for item in available}
        returned = {str(item["source_item_id"]) for item in records}
        return {
            "items": records, "count": len(records),
            "requested_source_item_ids": list(requested[: self.limits.max_items]),
            "missing_source_item_ids": [item for item in requested if item not in available_ids][: self.limits.max_items],
            "truncated_source_item_ids": [item for item in requested if item in available_ids and item not in returned][: self.limits.max_items],
            "has_more": len(records) < len(available), "read_only": True,
        }

    def search_source_items(self, project_id: str, query: str, source_item_ids: Sequence[str] | None = None) -> dict[str, Any]:
        normalized = bounded_text(query, 400).strip().casefold()
        if not normalized:
            return {"items": [], "count": 0, "returned_count": 0, "has_more": False, "query": "", "read_only": True}
        matches = [item for item in self._items(project_id, source_item_ids) if normalized in f"{item.key} {item.text}".casefold()]
        records = self._bounded_records(matches)
        return {
            "items": records, "count": len(records), "returned_count": len(records),
            "has_more": len(records) < len(matches), "query": normalized, "read_only": True,
        }

    list = list_source_items
    read = read_source_items
    search = search_source_items


class InMemoryCorpus:
    def __init__(self, items: Iterable[CorpusSourceItem | Mapping[str, Any]]) -> None:
        self.items = tuple(normalize_source_item(item) for item in items)

    def iter_source_items(self, project_id: str, source_item_ids: Sequence[str] | None = None) -> Iterable[CorpusSourceItem]:
        del project_id
        wanted = set(source_item_ids or ())
        return (item for item in self.items if not wanted or item.source_item_id in wanted)


__all__ = [
    "CorpusReader", "CorpusSourceItem", "CorpusToolLimits", "InMemoryCorpus",
    "ReadOnlyRemisCorpusTools", "bounded_text", "normalize_source_item", "safe_metadata",
]
