"""Pure validation and lossless repair-state handling for tree v2 extraction."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence

from scripts.core.services.context_tree_v2_contract import (
    ContextTreeV2Extraction,
    LocalFragment,
    UnresolvedFragmentReference,
)


class MissingFragmentReferenceError(ValueError):
    """Raised when a route points at a fragment absent from the same response."""

    def __init__(self, references: Sequence[tuple[str, str]]) -> None:
        self.references = tuple(references)
        detail = ", ".join(f"{unit_id}->{fragment_id}" for unit_id, fragment_id in references)
        super().__init__(f"Unit routes referenced unknown fragments: {detail}")


class ContextTreeV2ExtractionReconciliationService:
    """Keep local fragments and unit links intact while resolving missing cards."""

    @classmethod
    def validate(
        cls,
        extraction: ContextTreeV2Extraction,
        expected_unit_ids: Iterable[str],
        *,
        allow_unresolved: bool = False,
    ) -> tuple[tuple[str, str], ...]:
        expected = cls._unique_ids(expected_unit_ids, "expected local units")
        cls._validate_fragment_ids(extraction.local_fragments)
        cls._validate_routes(extraction, expected)
        cls._validate_fragment_units(extraction.local_fragments, expected)
        missing = cls.missing_fragment_references(extraction)
        if missing and not allow_unresolved:
            raise MissingFragmentReferenceError(missing)
        cls._validate_bindings(extraction, missing)
        return missing

    @classmethod
    def reconcile(
        cls,
        extraction: ContextTreeV2Extraction,
        expected_unit_ids: Iterable[str],
        repaired_fragments: Sequence[LocalFragment] = (),
        *,
        repair_attempts: int = 1,
    ) -> ContextTreeV2Extraction:
        """Merge only requested fragment definitions and preserve unresolved links."""

        if repair_attempts not in (0, 1):
            raise ValueError("tree v2 fragment repair is bounded to one attempt")
        expected = tuple(dict.fromkeys(str(item) for item in expected_unit_ids))
        requested = set(cls.missing_fragment_references(extraction))
        existing_ids = {fragment.fragment_id for fragment in extraction.local_fragments}
        additions = list(repaired_fragments)
        duplicate_additions = cls._duplicates(item.fragment_id for item in additions)
        if duplicate_additions:
            raise ValueError(f"Repaired fragment identities are duplicated: {duplicate_additions}")
        unexpected = {
            fragment.fragment_id for fragment in additions
            if (fragment.fragment_id not in {item[1] for item in requested})
            or fragment.fragment_id in existing_ids
        }
        if unexpected:
            raise ValueError(
                f"Fragment repair returned non-requested IDs: {sorted(unexpected)}"
            )
        merged = extraction.model_copy(update={
            "local_fragments": [*extraction.local_fragments, *additions],
            "unresolved_fragment_references": [],
        })
        remaining = cls.validate(merged, expected, allow_unresolved=True)
        unresolved = [
            UnresolvedFragmentReference(
                local_unit_id=unit_id,
                fragment_id=fragment_id,
                reason="targeted fragment repair did not return a valid definition",
                repair_attempts=repair_attempts,
            )
            for unit_id, fragment_id in remaining
        ]
        diagnostics = {
            **merged.diagnostics,
            "unresolved_fragment_reference_count": len(unresolved),
            "unresolved_fragment_ids": list(dict.fromkeys(
                item.fragment_id for item in unresolved
            )),
            "complete": not unresolved,
        }
        return merged.model_copy(update={
            "unresolved_fragment_references": unresolved,
            "diagnostics": diagnostics,
        })

    @staticmethod
    def missing_fragment_references(
        extraction: ContextTreeV2Extraction,
    ) -> tuple[tuple[str, str], ...]:
        known = {fragment.fragment_id for fragment in extraction.local_fragments}
        missing: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for route in extraction.unit_routes:
            for fragment_id in route.fragment_ids:
                reference = (route.local_unit_id, fragment_id)
                if fragment_id not in known and reference not in seen:
                    missing.append(reference)
                    seen.add(reference)
        return tuple(missing)

    @staticmethod
    def _unique_ids(values: Iterable[str], label: str) -> tuple[str, ...]:
        result = tuple(str(value) for value in values)
        duplicates = ContextTreeV2ExtractionReconciliationService._duplicates(result)
        if duplicates:
            raise ValueError(f"{label} are duplicated: {duplicates}")
        return result

    @classmethod
    def _validate_fragment_ids(cls, fragments: Sequence[LocalFragment]) -> None:
        duplicates = cls._duplicates(fragment.fragment_id for fragment in fragments)
        if duplicates:
            raise ValueError(f"Local fragment identities are duplicated: {duplicates}")

    @classmethod
    def _validate_routes(
        cls,
        extraction: ContextTreeV2Extraction,
        expected: Sequence[str],
    ) -> None:
        received = [route.local_unit_id for route in extraction.unit_routes]
        duplicates = cls._duplicates(received)
        missing = set(expected) - set(received)
        unexpected = set(received) - set(expected)
        if missing or unexpected or duplicates:
            raise ValueError(
                "Tree v2 unit route coverage invalid: "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}, "
                f"duplicate={duplicates}"
            )

    @classmethod
    def _validate_fragment_units(
        cls,
        fragments: Sequence[LocalFragment],
        expected: Sequence[str],
    ) -> None:
        expected_set = set(expected)
        invalid = {
            unit_id for fragment in fragments for unit_id in fragment.unit_ids
            if unit_id not in expected_set
        }
        if invalid:
            raise ValueError(
                f"Local fragments referenced unknown or edge units: {sorted(invalid)}"
            )

    @classmethod
    def _validate_bindings(
        cls,
        extraction: ContextTreeV2Extraction,
        missing: Sequence[tuple[str, str]],
    ) -> None:
        fragment_by_id = {
            fragment.fragment_id: fragment for fragment in extraction.local_fragments
        }
        unresolved = set(missing)
        invalid: list[str] = []
        for route in extraction.unit_routes:
            for fragment_id in route.fragment_ids:
                if (route.local_unit_id, fragment_id) in unresolved:
                    continue
                fragment = fragment_by_id.get(fragment_id)
                if fragment is None or route.local_unit_id not in fragment.unit_ids:
                    invalid.append(f"{route.local_unit_id}->{fragment_id}")
        if invalid:
            raise ValueError(
                "Unit routes and local fragment unit_ids disagree: "
                f"{sorted(invalid)}"
            )

    @staticmethod
    def _duplicates(values: Iterable[str]) -> list[str]:
        return sorted(value for value, count in Counter(values).items() if count > 1)
