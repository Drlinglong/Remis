"""Structure-aware source chunking for context analysis."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import SourceItem


class ContextChunkingPolicy:
    DEFAULT_MAX_ITEMS = 64
    MAX_ITEMS_LIMIT = 80
    DEFAULT_MAX_SOURCE_CHARS = 12000

    @classmethod
    def config(cls, analysis_config: dict[str, Any] | None) -> dict[str, int]:
        config = analysis_config or {}
        return {
            "max_items": cls._safe_int(
                config.get("max_items"), cls.DEFAULT_MAX_ITEMS, 1, cls.MAX_ITEMS_LIMIT,
            ),
            "max_source_chars": cls._safe_int(
                config.get("max_source_chars"), cls.DEFAULT_MAX_SOURCE_CHARS, 1, 200000,
            ),
        }

    @staticmethod
    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            return default
        return candidate if minimum <= candidate <= maximum else default

    @classmethod
    def chunks(
        cls,
        items: Iterable[SourceItem],
        *,
        max_items: int | None = None,
        max_source_chars: int | None = None,
        grouping_key: Callable[[SourceItem], str] | None = None,
    ) -> Iterable[tuple[SourceItem, ...]]:
        item_limit = max_items or cls.DEFAULT_MAX_ITEMS
        char_limit = max_source_chars or cls.DEFAULT_MAX_SOURCE_CHARS
        if not 1 <= item_limit <= cls.MAX_ITEMS_LIMIT:
            raise ValueError(f"max_items must be between 1 and {cls.MAX_ITEMS_LIMIT}")
        if char_limit < 1:
            raise ValueError("max_source_chars must be positive")
        key_function = grouping_key or cls.grouping_key
        current: list[SourceItem] = []
        current_chars = 0
        for group in cls.contiguous_groups(items, key_function):
            group_chars = sum(len(item.source_text) for item in group)
            oversized = (
                len(group) > item_limit
                or group_chars > char_limit
                or any(len(item.source_text) > char_limit for item in group)
            )
            if oversized:
                if current:
                    yield tuple(current)
                    current = []
                    current_chars = 0
                yield from cls.pack_group(group, item_limit, char_limit)
                continue
            if current and (
                len(current) + len(group) > item_limit
                or current_chars + group_chars > char_limit
            ):
                yield tuple(current)
                current = []
                current_chars = 0
            current.extend(group)
            current_chars += group_chars
        if current:
            yield tuple(current)

    @staticmethod
    def contiguous_groups(
        items: Iterable[SourceItem],
        grouping_key: Callable[[SourceItem], str],
    ) -> Iterable[tuple[SourceItem, ...]]:
        group: list[SourceItem] = []
        previous_key: str | None = None
        for item in items:
            current_key = grouping_key(item)
            if group and current_key != previous_key:
                yield tuple(group)
                group = []
            group.append(item)
            previous_key = current_key
        if group:
            yield tuple(group)

    @staticmethod
    def pack_group(
        group: Sequence[SourceItem], item_limit: int, char_limit: int,
    ) -> Iterable[tuple[SourceItem, ...]]:
        current: list[SourceItem] = []
        current_chars = 0
        for item in group:
            item_chars = len(item.source_text)
            if current and (len(current) >= item_limit or current_chars + item_chars > char_limit):
                yield tuple(current)
                current = []
                current_chars = 0
            if item_chars > char_limit:
                if current:
                    yield tuple(current)
                    current = []
                    current_chars = 0
                yield (item,)
                continue
            current.append(item)
            current_chars += item_chars
            if len(current) >= item_limit or current_chars >= char_limit:
                yield tuple(current)
                current = []
                current_chars = 0
        if current:
            yield tuple(current)

    @staticmethod
    def grouping_key(item: SourceItem) -> str:
        """Keep conservative local text units together without reordering."""
        return ContextLocalUnitBuilder.grouping_key(item)
