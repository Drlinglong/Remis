"""Expand model-authored local-unit assignments into release delivery edges."""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Any, Sequence

from scripts.core.neologism_extraction import StructuredNeologismExtraction
from scripts.schemas.context import (
    ContextAggregate,
    ContextDeliveryMembership,
    ContextSourceItem,
)


@dataclass(frozen=True)
class MembershipBuildResult:
    """Auditable delivery edges plus publication diagnostics."""

    memberships: tuple[ContextDeliveryMembership, ...]
    dropped_edges: tuple[dict[str, Any], ...] = ()
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def has_blockers(self) -> bool:
        return bool(self.diagnostics.get("blocking") or self.diagnostics.get("blockers"))

    @property
    def blockers(self) -> tuple[dict[str, Any], ...]:
        return tuple(self.diagnostics.get("blockers", ()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "memberships": [item.model_dump(mode="json") for item in self.memberships],
            "dropped_edges": [dict(item) for item in self.dropped_edges],
            "diagnostics": dict(self.diagnostics),
        }

    def __len__(self) -> int:
        return len(self.memberships)

    def __iter__(self):
        return iter(self.memberships)


class ContextDeliveryMembershipError(ValueError):
    """Raised by the workflow caller before a partial release can publish."""

    def __init__(self, result: MembershipBuildResult):
        self.result = result
        self.detail = {
            "code": "context_delivery_membership_incomplete",
            "message": "Context delivery membership validation blocked publication.",
            "allowed_actions": ["review_context_assignments"],
            "membership": result.as_dict(),
        }
        super().__init__(self.detail["message"])


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
        *,
        expected_local_unit_ids: Sequence[str] | None = None,
    ) -> MembershipBuildResult:
        aggregates_by_key = {item.aggregate_key: item for item in aggregates}
        edges: dict[tuple[str, str], ContextDeliveryMembership] = {}
        dropped_edges: list[dict[str, Any]] = []
        assignment_ids: list[str] = []
        for extraction in extractions:
            for assignment in extraction.delivery_assignments:
                assignment_ids.append(assignment.local_unit_id)
                if assignment.assignment_state == "unassigned":
                    continue
                for link in assignment.links:
                    aggregate_key = f"event:{link.event_chain_id.strip().casefold()}"
                    aggregate = aggregates_by_key.get(aggregate_key)
                    source_item_ids = assignment.source_item_ids or [None]
                    for source_item_id in source_item_ids:
                        source_known = source_item_id in sources
                        if link.relation == "theme_related":
                            dropped_edges.append(cls._dropped_edge(
                                assignment,
                                link,
                                source_item_id,
                                aggregate_key,
                                code="theme_related_not_delivered",
                                blocking=False,
                                aggregate_known=aggregate is not None,
                                source_known=source_known,
                            ))
                            continue
                        if aggregate is None:
                            dropped_edges.append(cls._dropped_edge(
                                assignment,
                                link,
                                source_item_id,
                                aggregate_key,
                                code=cls._unknown_aggregate_code(link.relation),
                                blocking=True,
                                aggregate_known=False,
                                source_known=source_known,
                            ))
                            continue
                        if source_item_id is None:
                            dropped_edges.append(cls._dropped_edge(
                                assignment,
                                link,
                                source_item_id,
                                aggregate_key,
                                code="missing_source_item_ids",
                                blocking=True,
                                aggregate_known=True,
                                source_known=False,
                            ))
                            continue
                        if not source_known:
                            dropped_edges.append(cls._dropped_edge(
                                assignment,
                                link,
                                source_item_id,
                                aggregate_key,
                                code="unknown_source_item",
                                blocking=True,
                                aggregate_known=True,
                                source_known=False,
                            ))
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
        blocking_edges = [item for item in dropped_edges if item["blocking"]]
        diagnostics = cls._diagnostics(
            dropped_edges, blocking_edges, assignment_ids, expected_local_unit_ids,
        )
        return MembershipBuildResult(
            memberships=tuple(sorted(
                edges.values(),
                key=lambda item: (item.aggregate_id, item.source_item_id),
            )),
            dropped_edges=tuple(dropped_edges),
            diagnostics=diagnostics,
        )

    @classmethod
    def _diagnostics(
        cls,
        dropped_edges: Sequence[dict[str, Any]],
        blocking_edges: Sequence[dict[str, Any]],
        assignment_ids: Sequence[str],
        expected_local_unit_ids: Sequence[str] | None,
    ) -> dict[str, Any]:
        completeness_blockers = cls._assignment_completeness(
            assignment_ids, expected_local_unit_ids,
        )
        blockers = [*blocking_edges, *completeness_blockers]
        assignment_counts = Counter(assignment_ids)
        return {
            "blocking": bool(blockers),
            "blockers": blockers,
            "blocking_edge_count": len(blocking_edges),
            "dropped_edge_count": len(dropped_edges),
            "theme_related_count": sum(
                item["code"] == "theme_related_not_delivered"
                for item in dropped_edges
            ),
            "unknown_event_aggregate_count": sum(
                item["blocking"] and not item["aggregate_known"]
                for item in dropped_edges
            ),
            "unknown_source_item_count": sum(
                item["code"] == "unknown_source_item"
                for item in dropped_edges
            ),
            "assignment_completeness": {
                "expected_local_unit_count": (
                    len(expected_local_unit_ids)
                    if expected_local_unit_ids is not None else None
                ),
                "received_local_unit_count": len(assignment_ids),
                "duplicate_local_unit_ids": sorted(
                    unit_id for unit_id, count in assignment_counts.items() if count > 1
                ),
                "missing_local_unit_ids": sorted(
                    set(expected_local_unit_ids or ()) - set(assignment_ids)
                ) if expected_local_unit_ids is not None else [],
                "unexpected_local_unit_ids": sorted(
                    set(assignment_ids) - set(expected_local_unit_ids or ())
                ) if expected_local_unit_ids is not None else [],
                "verified": expected_local_unit_ids is not None,
            },
        }

    @staticmethod
    def _assignment_completeness(
        assignment_ids: Sequence[str],
        expected_local_unit_ids: Sequence[str] | None,
    ) -> list[dict[str, Any]]:
        if expected_local_unit_ids is None:
            return []
        counts = Counter(assignment_ids)
        expected = set(expected_local_unit_ids)
        duplicate = sorted(unit_id for unit_id, count in counts.items() if count > 1)
        missing = sorted(expected - set(assignment_ids))
        unexpected = sorted(set(assignment_ids) - expected)
        if not (duplicate or missing or unexpected):
            return []
        return [{
            "code": "assignment_local_unit_incomplete",
            "blocking": True,
            "duplicate_local_unit_ids": duplicate,
            "missing_local_unit_ids": missing,
            "unexpected_local_unit_ids": unexpected,
        }]

    @staticmethod
    def _dropped_edge(
        assignment: Any,
        link: Any,
        source_item_id: str | None,
        aggregate_key: str,
        *,
        code: str,
        blocking: bool,
        aggregate_known: bool,
        source_known: bool,
    ) -> dict[str, Any]:
        return {
            "local_unit_id": assignment.local_unit_id,
            "aggregate_key": aggregate_key,
            "source_item_id": source_item_id,
            "role": link.relation,
            "code": code,
            "blocking": blocking,
            "aggregate_known": aggregate_known,
            "source_known": source_known,
        }

    @staticmethod
    def _unknown_aggregate_code(relation: str) -> str:
        return {
            "primary_member": "unknown_primary_membership_target",
            "supporting_context": "unknown_supporting_context_target",
        }.get(relation, "unknown_event_aggregate")

    @classmethod
    def _stronger(
        cls,
        candidate: ContextDeliveryMembership,
        current: ContextDeliveryMembership,
    ) -> bool:
        candidate_rank = cls._ROLE_PRIORITY[candidate.role]
        current_rank = cls._ROLE_PRIORITY[current.role]
        return (candidate_rank, candidate.confidence) > (current_rank, current.confidence)
