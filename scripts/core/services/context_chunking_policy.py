"""Structure-aware source chunking for context analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_tree_v2_contract import ChunkEdgeMetadata


@dataclass(frozen=True)
class ContextUnitChunk:
    """Whole core units plus read-only neighbouring units for boundary context."""

    core_units: tuple[LocalTextUnit, ...]
    edge_units: tuple[LocalTextUnit, ...]
    chunk_index: int = 0
    chunk_count: int = 1

    @property
    def source_items(self) -> tuple[SourceItem, ...]:
        items = {
            item.source_item_id: item
            for unit in (*self.core_units, *self.edge_units)
            for item in unit.items
        }
        return tuple(sorted(items.values(), key=lambda item: item.source_order))

    @property
    def edge_metadata(self) -> ChunkEdgeMetadata:
        """Expose boundary facts without making callers infer them from tuples."""

        core_ids = [unit.unit_id for unit in self.core_units]
        before_ids = [
            unit.unit_id for unit in self.edge_units
            if unit.unit_id not in core_ids
            and self._unit_order(unit) < self._first_core_order()
        ]
        after_ids = [
            unit.unit_id for unit in self.edge_units
            if unit.unit_id not in core_ids
            and self._unit_order(unit) > self._last_core_order()
        ]
        return ChunkEdgeMetadata(
            chunk_index=self.chunk_index,
            chunk_count=self.chunk_count,
            core_unit_ids=core_ids,
            edge_before_unit_ids=before_ids,
            edge_after_unit_ids=after_ids,
            has_previous_core_chunk=self.chunk_index > 0,
            has_next_core_chunk=self.chunk_index + 1 < self.chunk_count,
        )

    def _first_core_order(self) -> int:
        return min(self._unit_order(unit) for unit in self.core_units)

    def _last_core_order(self) -> int:
        return max(self._unit_order(unit) for unit in self.core_units)

    @staticmethod
    def _unit_order(unit: LocalTextUnit) -> int:
        match = re.fullmatch(r"unit_(\d+)", unit.unit_id)
        if match:
            return int(match.group(1))
        orders = [
            int(getattr(item, "source_order", 0) or 0)
            for item in unit.items
        ]
        return min(orders, default=0)


class ContextChunkingPolicy:
    DEFAULT_MAX_ITEMS = 64
    MAX_ITEMS_LIMIT = 80
    DEFAULT_MAX_SOURCE_CHARS = 12000
    DEFAULT_EDGE_UNITS = 3

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

    @classmethod
    def unit_chunks(
        cls,
        units: Sequence[LocalTextUnit],
        *,
        max_items: int | None = None,
        max_source_chars: int | None = None,
        edge_units: int = DEFAULT_EDGE_UNITS,
    ) -> tuple[ContextUnitChunk, ...]:
        """Chunk globally stable units without ever splitting a local unit."""

        item_limit = max_items or cls.DEFAULT_MAX_ITEMS
        char_limit = max_source_chars or cls.DEFAULT_MAX_SOURCE_CHARS
        if not 1 <= item_limit <= cls.MAX_ITEMS_LIMIT:
            raise ValueError(f"max_items must be between 1 and {cls.MAX_ITEMS_LIMIT}")
        if char_limit < 1:
            raise ValueError("max_source_chars must be positive")
        if not 0 <= edge_units <= 4:
            raise ValueError("edge_units must be between 0 and 4")

        core_groups: list[tuple[LocalTextUnit, ...]] = []
        current: list[LocalTextUnit] = []
        current_items = 0
        current_chars = 0
        for unit in units:
            unit_items = len(unit.items)
            unit_chars = sum(len(item.source_text) for item in unit.items)
            if current and (
                current_items + unit_items > item_limit
                or current_chars + unit_chars > char_limit
            ):
                core_groups.append(tuple(current))
                current = []
                current_items = 0
                current_chars = 0
            current.append(unit)
            current_items += unit_items
            current_chars += unit_chars
        if current:
            core_groups.append(tuple(current))

        unit_positions = {unit.unit_id: index for index, unit in enumerate(units)}
        planned: list[ContextUnitChunk] = []
        chunk_count = len(core_groups)
        for chunk_index, core in enumerate(core_groups):
            first = unit_positions[core[0].unit_id]
            last = unit_positions[core[-1].unit_id]
            before = units[max(0, first - edge_units):first]
            after = units[last + 1:last + 1 + edge_units]
            planned.append(ContextUnitChunk(
                core_units=core,
                edge_units=tuple((*before, *after)),
                chunk_index=chunk_index,
                chunk_count=chunk_count,
            ))
        return tuple(planned)

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
