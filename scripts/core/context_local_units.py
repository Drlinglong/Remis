"""Conservative local text units and model-authored delivery assignments."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field


DeliveryRole = Literal[
    "primary_member",
    "supporting_context",
    "theme_related",
    "unassigned",
]


class DeliveryAssignment(BaseModel):
    """One exhaustive local-unit assignment returned by the extraction model."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    local_unit_id: str = Field(pattern=r"^unit_\d+$")
    event_chain_ids: list[str] = Field(default_factory=list, max_length=5)
    role: DeliveryRole
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: str | None = Field(default=None, max_length=500)
    source_item_ids: list[str] = Field(default_factory=list, max_length=80)


@dataclass(frozen=True)
class LocalTextUnit:
    """Adjacent localization entries that clearly describe one local object/node."""

    unit_id: str
    unit_key: str
    items: tuple[Any, ...]

    def prompt_payload(self, source_aliases: dict[str, str]) -> dict[str, Any]:
        return {
            "local_unit_id": self.unit_id,
            "derived_unit_key": self.unit_key.split("::", 1)[-1],
            "source_item_ids": [source_aliases[item.source_item_id] for item in self.items],
            "item_keys": [item.item_key for item in self.items if item.item_key],
        }


class ContextLocalUnitBuilder:
    """Build local units without pretending that key shape proves story membership."""

    _VERSION_SUFFIX = re.compile(r":\d+$")
    _STRUCTURAL_SUFFIX = re.compile(
        r"(?:[._](?:title|name|desc|description|tooltip))$",
        flags=re.IGNORECASE,
    )

    @classmethod
    def grouping_key(cls, item: Any) -> str:
        raw_key = cls._VERSION_SUFFIX.sub("", str(item.item_key or "").strip())
        normalized = raw_key.casefold()
        segments = [segment for segment in normalized.split(".") if segment]
        numeric_index = next(
            (index for index, segment in enumerate(segments) if segment.isdigit()),
            None,
        )
        if numeric_index is not None:
            local_key = ".".join(segments[: numeric_index + 1])
        else:
            local_key = cls._STRUCTURAL_SUFFIX.sub("", normalized) or normalized
        if not local_key:
            local_key = f"source-order-{getattr(item, 'source_order', 0)}"
        return f"{str(item.relative_path).casefold()}::{local_key}"

    @classmethod
    def build(cls, source_items: Sequence[Any]) -> tuple[LocalTextUnit, ...]:
        units: list[LocalTextUnit] = []
        current_items: list[Any] = []
        current_key: str | None = None
        for item in source_items:
            item_key = cls.grouping_key(item)
            if current_items and item_key != current_key:
                units.append(cls._unit(len(units), current_key or "", current_items))
                current_items = []
            current_key = item_key
            current_items.append(item)
        if current_items:
            units.append(cls._unit(len(units), current_key or "", current_items))
        return tuple(units)

    @staticmethod
    def _unit(index: int, unit_key: str, items: list[Any]) -> LocalTextUnit:
        return LocalTextUnit(
            unit_id=f"unit_{index}",
            unit_key=unit_key,
            items=tuple(items),
        )
