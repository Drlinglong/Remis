"""Deterministic contract for exhaustive local-unit delivery assignments."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink, LocalTextUnit


def normalize_delivery_assignments(
    assignments: Iterable[DeliveryAssignment],
    core_units: Sequence[LocalTextUnit],
    valid_chain_ids: Iterable[str],
) -> list[DeliveryAssignment]:
    """Require exactly one model decision per core unit, then expand source IDs."""

    received = list(assignments)
    expected_ids = [unit.unit_id for unit in core_units]
    received_ids = [assignment.local_unit_id for assignment in received]
    diagnostics = _assignment_diagnostics(expected_ids, received_ids)
    if any(diagnostics.values()):
        raise ValueError(_format_diagnostics(diagnostics))

    canonical_chains = {chain_id.casefold(): chain_id for chain_id in valid_chain_ids}
    by_unit = {assignment.local_unit_id: assignment for assignment in received}
    normalized: list[DeliveryAssignment] = []
    for unit in core_units:
        assignment = by_unit[unit.unit_id]
        links = _normalize_links(assignment.links, canonical_chains)
        if assignment.assignment_state == "assigned" and not links:
            raise ValueError(f"assigned local unit has no valid links: {unit.unit_id}")
        if assignment.assignment_state == "unassigned" and assignment.links:
            raise ValueError(f"unassigned local unit returned links: {unit.unit_id}")
        normalized.append(DeliveryAssignment(
            local_unit_id=unit.unit_id,
            links=links,
            assignment_state=assignment.assignment_state,
            source_item_ids=[item.source_item_id for item in unit.items],
        ))
    return normalized


def _normalize_links(
    links: Iterable[DeliveryLink],
    canonical_chains: dict[str, str],
) -> list[DeliveryLink]:
    normalized: list[DeliveryLink] = []
    seen: set[tuple[str, str]] = set()
    for link in links:
        chain_id = canonical_chains.get(link.event_chain_id.casefold())
        if chain_id is None:
            raise ValueError(f"delivery link references unknown local chain: {link.event_chain_id}")
        identity = (chain_id.casefold(), link.relation)
        if identity in seen:
            raise ValueError(
                f"duplicate delivery link: {chain_id}/{link.relation}"
            )
        seen.add(identity)
        normalized.append(link.model_copy(update={"event_chain_id": chain_id}))
    return normalized


def _assignment_diagnostics(
    expected_ids: Sequence[str], received_ids: Sequence[str],
) -> dict[str, list[str]]:
    expected = Counter(expected_ids)
    received = Counter(received_ids)
    return {
        "missing": list((expected - received).elements()),
        "unexpected": list((received - expected).elements()),
        "duplicate": sorted(unit_id for unit_id, count in received.items() if count > 1),
    }


def _format_diagnostics(diagnostics: dict[str, list[str]]) -> str:
    detail = "; ".join(
        f"{name}={values[:10]}" for name, values in diagnostics.items()
    )
    return f"delivery assignment set mismatch ({detail})"
