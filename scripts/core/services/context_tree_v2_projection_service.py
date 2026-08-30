"""Deterministic unit -> fragment -> group projection for tree v2 delivery."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from scripts.core.services.context_tree_v2_contract import (
    ContextTreeCatalog,
    ProjectedUnitRoute,
    TreeCatalogResult,
    TreeProjectionResult,
    UnitRoute,
    UnresolvedFragmentReference,
)


class ContextTreeV2ProjectionService:
    """Project extraction routes without a final assignment model call."""

    @classmethod
    def project(
        cls,
        unit_routes: Sequence[UnitRoute],
        catalog: ContextTreeCatalog | TreeCatalogResult,
        *,
        expected_unit_ids: Iterable[str] | None = None,
    ) -> TreeProjectionResult:
        tree = catalog.catalog if isinstance(catalog, TreeCatalogResult) else catalog
        routes = list(unit_routes)
        cls._validate_routes(routes, expected_unit_ids)
        group_by_fragment = cls._group_by_fragment(tree)
        unresolved_catalog_ids = set(tree.unresolved_fragment_ids)
        projected: list[ProjectedUnitRoute] = []
        unresolved: list[UnresolvedFragmentReference] = []
        for route in routes:
            if route.route != "narrative":
                projected.append(ProjectedUnitRoute(
                    local_unit_id=route.local_unit_id,
                    route=route.route,
                    fragment_ids=[],
                    group_ids=[],
                    receives_event_context=False,
                ))
                continue
            group_ids: set[str] = set()
            unresolved_ids: list[str] = []
            for fragment_id in route.fragment_ids:
                if fragment_id in group_by_fragment:
                    group_ids.add(group_by_fragment[fragment_id])
                    continue
                unresolved_ids.append(fragment_id)
                unresolved.append(UnresolvedFragmentReference(
                    local_unit_id=route.local_unit_id,
                    fragment_id=fragment_id,
                    reason=(
                        "catalog explicitly retained this fragment as unresolved"
                        if fragment_id in unresolved_catalog_ids
                        else "catalog did not contain the referenced fragment"
                    ),
                    repair_attempts=0,
                ))
            projected.append(ProjectedUnitRoute(
                local_unit_id=route.local_unit_id,
                route=route.route,
                fragment_ids=list(route.fragment_ids),
                group_ids=sorted(group_ids),
                unresolved_fragment_ids=unresolved_ids,
                receives_event_context=bool(group_ids) and not unresolved_ids,
            ))
        return TreeProjectionResult(
            unit_routes=projected,
            unresolved_fragment_references=unresolved,
        )

    @staticmethod
    def _group_by_fragment(catalog: ContextTreeCatalog) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for group in catalog.groups:
            for fragment_id in group.fragment_ids:
                if fragment_id in mapping:
                    raise ValueError(
                        f"Fragment {fragment_id} belongs to multiple event groups"
                    )
                mapping[fragment_id] = group.group_id
        return mapping

    @classmethod
    def _validate_routes(
        cls,
        routes: Sequence[UnitRoute],
        expected_unit_ids: Iterable[str] | None,
    ) -> None:
        received = [route.local_unit_id for route in routes]
        duplicates = sorted(
            unit_id for unit_id, count in Counter(received).items() if count > 1
        )
        if duplicates:
            raise ValueError(f"Projected unit routes are duplicated: {duplicates}")
        if expected_unit_ids is None:
            return
        expected = set(str(item) for item in expected_unit_ids)
        missing = expected - set(received)
        unexpected = set(received) - expected
        if missing or unexpected:
            raise ValueError(
                "Projected unit route coverage invalid: "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
            )
