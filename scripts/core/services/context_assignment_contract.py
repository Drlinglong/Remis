"""Deterministic normalization for model-authored local delivery hints."""

from __future__ import annotations

from typing import Iterable, Sequence

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink, LocalTextUnit


def normalize_sparse_delivery_hints(
    assignments: Iterable[DeliveryAssignment],
    core_units: Sequence[LocalTextUnit],
    valid_chain_ids: Iterable[str],
) -> tuple[list[DeliveryAssignment], dict[str, list[str]]]:
    """Keep grounded positive local hints without pretending they are final coverage."""

    expected_units = {unit.unit_id: unit for unit in core_units}
    canonical_chains = {chain_id.casefold(): chain_id for chain_id in valid_chain_ids}
    grouped: dict[str, list[DeliveryAssignment]] = {}
    unexpected: list[str] = []
    for assignment in assignments:
        if assignment.local_unit_id not in expected_units:
            unexpected.append(assignment.local_unit_id)
            continue
        grouped.setdefault(assignment.local_unit_id, []).append(assignment)

    normalized: list[DeliveryAssignment] = []
    unknown_links: list[str] = []
    duplicate_units: list[str] = []
    for unit in core_units:
        candidates = grouped.get(unit.unit_id, [])
        if len(candidates) > 1:
            duplicate_units.append(unit.unit_id)
        links = _merge_sparse_links(candidates, canonical_chains, unknown_links)
        if not links:
            continue
        normalized.append(DeliveryAssignment(
            local_unit_id=unit.unit_id,
            links=links,
            assignment_state="assigned",
            source_item_ids=[item.source_item_id for item in unit.items],
        ))

    hinted_ids = {assignment.local_unit_id for assignment in normalized}
    diagnostics = {
        "local_hint_omitted_unit_ids": [
            unit.unit_id for unit in core_units if unit.unit_id not in hinted_ids
        ],
        "local_hint_unexpected_unit_ids": sorted(set(unexpected)),
        "local_hint_duplicate_unit_ids": duplicate_units,
        "dropped_unknown_local_chain_links": unknown_links,
    }
    return normalized, diagnostics


def _merge_sparse_links(
    assignments: Sequence[DeliveryAssignment],
    canonical_chains: dict[str, str],
    unknown_links: list[str],
) -> list[DeliveryLink]:
    normalized: list[DeliveryLink] = []
    seen: set[tuple[str, str]] = set()
    for assignment in assignments:
        if assignment.assignment_state != "assigned":
            continue
        for link in assignment.links:
            chain_id = canonical_chains.get(link.event_chain_id.casefold())
            if chain_id is None:
                unknown_links.append(
                    f"{assignment.local_unit_id}:{link.event_chain_id}"
                )
                continue
            identity = (chain_id.casefold(), link.relation)
            if identity in seen:
                continue
            seen.add(identity)
            normalized.append(link.model_copy(update={"event_chain_id": chain_id}))
    return normalized
