"""Expand model-authored local-unit assignments into release delivery edges."""

from __future__ import annotations

from typing import Sequence

from scripts.core.neologism_extraction import StructuredNeologismExtraction
from scripts.schemas.context import (
    ContextAggregate,
    ContextDeliveryMembership,
    ContextSourceItem,
)


class ContextDeliveryMembershipService:
    """Map local event-chain labels onto the aggregates created for the release."""

    _ROLE_PRIORITY = {
        "theme_related": 0,
        "supporting_context": 1,
        "primary_member": 2,
    }

    @classmethod
    def build(
        cls,
        extractions: Sequence[StructuredNeologismExtraction],
        aggregates: Sequence[ContextAggregate],
        sources: dict[str, ContextSourceItem],
    ) -> list[ContextDeliveryMembership]:
        aggregates_by_key = {item.aggregate_key: item for item in aggregates}
        edges: dict[tuple[str, str], ContextDeliveryMembership] = {}
        for extraction in extractions:
            for assignment in extraction.delivery_assignments:
                if assignment.assignment_state == "unassigned":
                    continue
                for link in assignment.links:
                    aggregate = aggregates_by_key.get(
                        f"event:{link.event_chain_id.strip().casefold()}"
                    )
                    if aggregate is None:
                        continue
                    for source_item_id in assignment.source_item_ids:
                        if source_item_id not in sources:
                            continue
                        candidate = ContextDeliveryMembership(
                            aggregate_id=aggregate.aggregate_id,
                            source_item_id=source_item_id,
                            role=link.relation,
                            confidence=link.confidence,
                            reasoning=link.reasoning,
                        )
                        key = (aggregate.aggregate_id, source_item_id)
                        current = edges.get(key)
                        if current is None or cls._stronger(candidate, current):
                            edges[key] = candidate
        return sorted(
            edges.values(),
            key=lambda item: (item.aggregate_id, item.source_item_id),
        )

    @classmethod
    def _stronger(
        cls,
        candidate: ContextDeliveryMembership,
        current: ContextDeliveryMembership,
    ) -> bool:
        candidate_rank = cls._ROLE_PRIORITY[candidate.role]
        current_rank = cls._ROLE_PRIORITY[current.role]
        return (candidate_rank, candidate.confidence) > (current_rank, current.confidence)
