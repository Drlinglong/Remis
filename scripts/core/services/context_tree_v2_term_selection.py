"""Variant ordering and approval state for the terms-only result boundary."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from scripts.core.neologism_extraction import SourceEvidence


class TermOnlyVariant(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    variant_id: str = Field(min_length=1, max_length=500)
    batch_index: int = Field(ge=0)
    term_index: int = Field(ge=0)
    original: str = Field(min_length=1, max_length=200)
    suggestion: str | None = Field(default=None, max_length=500)
    reasoning: str | None = Field(default=None, max_length=2_000)
    evidence: tuple[SourceEvidence, ...] = Field(min_length=1, max_length=5)

    @property
    def translation(self) -> str | None:
        return self.suggestion

    @property
    def explanation(self) -> str | None:
        return self.reasoning

    @property
    def order_key(self) -> tuple[Any, ...]:
        return (
            self.batch_index,
            self.term_index,
            self.suggestion or "",
            self.reasoning or "",
            tuple(_evidence_sort_key(item) for item in self.evidence),
            self.variant_id,
        )


class TermVariantSelectionState(BaseModel):
    """Mutable review state: approval keeps exactly one variant."""

    model_config = ConfigDict(extra="forbid")

    variants: list[TermOnlyVariant] = Field(min_length=1, max_length=100)
    selected_variant_id: str | None = None

    @property
    def first_variant(self) -> TermOnlyVariant:
        return self.variants[0]

    @property
    def pending_variants(self) -> tuple[TermOnlyVariant, ...]:
        return tuple(self.variants) if self.selected_variant_id is None else ()

    @property
    def selected_variant(self) -> TermOnlyVariant | None:
        if self.selected_variant_id is None:
            return None
        return next(
            (variant for variant in self.variants if variant.variant_id == self.selected_variant_id),
            None,
        )

    def approve(self, variant_id: str | None = None) -> TermOnlyVariant:
        selected_id = variant_id or self.first_variant.variant_id
        selected = next(
            (variant for variant in self.variants if variant.variant_id == selected_id),
            None,
        )
        if selected is None:
            raise KeyError(f"Unknown term variant: {selected_id}")
        self.selected_variant_id = selected.variant_id
        self.variants = [selected]
        return selected


class TermOnlyTerm(TermVariantSelectionState):
    normalized_key: str = Field(min_length=1, max_length=500)
    original: str = Field(min_length=1, max_length=200)
    evidence: tuple[SourceEvidence, ...] = Field(min_length=1, max_length=500)


def _evidence_sort_key(value: SourceEvidence) -> tuple[Any, ...]:
    return (
        value.source_item_id,
        value.relative_path,
        value.item_key or "",
        value.source_order if value.source_order is not None else -1,
        value.snippet or "",
        value.provenance,
    )


__all__ = ["TermOnlyTerm", "TermOnlyVariant", "TermVariantSelectionState"]
