"""Deterministic governance for source-grounded Mod Context candidates."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from scripts.core.context_local_units import DeliveryAssignment, LocalTextUnit
from scripts.core.neologism_extraction import SourceItem, StructuredNeologismExtraction
from scripts.core.services.context_candidate_rules import ContextCandidateRules
from scripts.schemas.context_candidate import (
    ContextCandidate,
    ContextCandidateGovernanceResult,
    candidate_aggregate_key,
    normalized_match_key,
)


class ContextCandidateGovernanceService:
    """Orchestrate deterministic candidate rules and preserve audit boundaries."""

    def __init__(self, source_language: str = "en") -> None:
        self.source_language = source_language

    def aggregate_key_for_surface(
        self,
        surface: str,
        *,
        source_language: str | None = None,
    ) -> str:
        """Return the stable aggregate key without consulting model semantics."""

        return candidate_aggregate_key(surface, source_language or self.source_language)

    def govern(
        self,
        extractions: Sequence[StructuredNeologismExtraction] = (),
        source_items: Sequence[SourceItem] = (),
        local_units: Sequence[LocalTextUnit] = (),
        final_delivery_assignments: Sequence[DeliveryAssignment] | None = None,
        *,
        final_assignments: Sequence[DeliveryAssignment] | None = None,
        final_delivery_links: Sequence[DeliveryAssignment] | None = None,
        final_local_unit_delivery_links: Sequence[DeliveryAssignment] | None = None,
        existing_glossary_matches: Iterable[Any] = (),
        existing_glossary_match_keys: Iterable[Any] = (),
        glossary_match_keys: Iterable[Any] = (),
        glossary_matches: Iterable[Any] = (),
        user_confirmed_match_keys: Iterable[Any] = (),
        user_policy_overrides: Mapping[str, Any] | None = None,
        user_overrides: Mapping[str, Any] | None = None,
        raw_extraction_checkpoints: Sequence[Mapping[str, Any]] | None = None,
        source_aliases: Mapping[str, str] | None = None,
        source_language: str | None = None,
    ) -> ContextCandidateGovernanceResult:
        """Govern candidates using only deterministic backend-owned evidence."""

        language = source_language or self.source_language
        rules = ContextCandidateRules()
        items = self._coerce_source_items(source_items)
        units = tuple(local_units)
        extractions = self._coerce_extractions(extractions)
        assignments = self._select_assignments(
            final_delivery_assignments,
            final_assignments,
            final_delivery_links,
            final_local_unit_delivery_links,
        )
        source_lookup = {item.source_item_id: item for item in items}
        aliases = self._source_aliases(items, source_aliases)
        aggregates, keys_by_batch, dropped = rules.collect_aggregates(
            extractions, source_lookup, language
        )
        unit_by_source, source_ids_by_unit = rules.unit_indexes(units)
        chain_by_unit = rules.final_chain_index(assignments)
        glossary_keys = rules.normalized_key_set(
            (
                *rules.as_values(existing_glossary_matches),
                *rules.as_values(existing_glossary_match_keys),
                *rules.as_values(glossary_match_keys),
                *rules.as_values(glossary_matches),
            ),
            language,
        )
        confirmed_keys = rules.normalized_key_set(user_confirmed_match_keys, language)
        overrides = {
            **(user_overrides or {}),
            **(user_policy_overrides or {}),
        }
        candidates = tuple(
            rules.build_candidate(
                aggregate,
                items,
                source_lookup,
                unit_by_source,
                source_ids_by_unit,
                chain_by_unit,
                glossary_keys,
                confirmed_keys,
                overrides,
                language,
            )
            for aggregate in aggregates.values()
        )
        policies = {
            candidate.aggregate_key: rules.policy_for(candidate)
            for candidate in candidates
        }
        governed, raw_checkpoints = self._governed_extractions(
            extractions,
            aliases,
            keys_by_batch,
            raw_extraction_checkpoints,
        )
        synthesis_keys = tuple(
            candidate.aggregate_key
            for candidate in candidates
            if candidate.summary_eligible or rules.override_flag(
                overrides, candidate.normalized_match_key, language, "synthesis_eligible"
            )
        )
        glossary_eligible = tuple(
            candidate.normalized_match_key
            for candidate in candidates
            if candidate.glossary_eligible
        )
        report = self._build_report(
            candidates,
            raw_checkpoints,
            aliases,
            dropped,
            bool(units),
        )
        return ContextCandidateGovernanceResult(
            candidates=candidates,
            policy_by_aggregate_key=policies,
            governed_extractions=governed,
            synthesis_eligible_aggregate_keys=synthesis_keys,
            glossary_eligible_match_keys=glossary_eligible,
            source_aliases=aliases,
            raw_extraction_checkpoints=raw_checkpoints,
            source_language=language,
            report=report,
        )

    @staticmethod
    def _coerce_source_items(source_items: Sequence[SourceItem]) -> tuple[SourceItem, ...]:
        items = tuple(
            item if isinstance(item, SourceItem) else SourceItem.model_validate(item)
            for item in source_items
        )
        ids = [item.source_item_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Source item identities must be unique for candidate governance")
        return items

    @staticmethod
    def _coerce_extractions(
        extractions: Sequence[StructuredNeologismExtraction],
    ) -> tuple[StructuredNeologismExtraction, ...]:
        return tuple(
            extraction
            if isinstance(extraction, StructuredNeologismExtraction)
            else StructuredNeologismExtraction.model_validate(extraction)
            for extraction in extractions
        )

    @staticmethod
    def _select_assignments(
        final_delivery_assignments: Sequence[DeliveryAssignment] | None,
        final_assignments: Sequence[DeliveryAssignment] | None,
        final_delivery_links: Sequence[DeliveryAssignment] | None,
        final_local_unit_delivery_links: Sequence[DeliveryAssignment] | None,
    ) -> tuple[DeliveryAssignment, ...]:
        selected = next(
            (
                value
                for value in (
                    final_delivery_assignments,
                    final_assignments,
                    final_delivery_links,
                    final_local_unit_delivery_links,
                )
                if value is not None
            ),
            (),
        )
        return tuple(
            item if isinstance(item, DeliveryAssignment) else DeliveryAssignment.model_validate(item)
            for item in selected
        )

    @staticmethod
    def _source_aliases(
        items: Sequence[SourceItem],
        supplied: Mapping[str, str] | None,
    ) -> dict[str, str]:
        if supplied is not None:
            return {str(key): str(value) for key, value in supplied.items()}
        return {
            item.source_item_id: f"source_{index}"
            for index, item in enumerate(items)
        }

    def _governed_extractions(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        aliases: Mapping[str, str],
        keys_by_batch: Mapping[int, Sequence[str]],
        raw_checkpoints: Sequence[Mapping[str, Any]] | None,
    ) -> tuple[tuple[StructuredNeologismExtraction, ...], tuple[dict[str, Any], ...]]:
        governed: list[StructuredNeologismExtraction] = []
        checkpoints: list[dict[str, Any]] = []
        for batch_index, extraction in enumerate(extractions):
            if raw_checkpoints is not None and batch_index < len(raw_checkpoints):
                raw = dict(raw_checkpoints[batch_index])
            else:
                raw = extraction.model_dump(mode="json")
            checkpoints.append(raw)
            diagnostics = {
                **extraction.diagnostics,
                "candidate_governance": {
                    "source_aliases": dict(aliases),
                    "candidate_aggregate_keys": tuple(keys_by_batch.get(batch_index, ())),
                },
            }
            governed.append(extraction.model_copy(update={"diagnostics": diagnostics}))
        return tuple(governed), tuple(checkpoints)

    @staticmethod
    def _build_report(
        candidates: Sequence[ContextCandidate],
        raw_checkpoints: Sequence[Mapping[str, Any]],
        aliases: Mapping[str, str],
        dropped: Sequence[Mapping[str, Any]],
        has_local_units: bool,
    ) -> dict[str, Any]:
        return {
            "schema_version": "context-candidate-governance-v1",
            "coverage_authority": "backend_computed",
            "policy_coverage_source": "local_unit_coverage" if has_local_units else "source_item_coverage",
            "candidate_count": len(candidates),
            "alias_merge_count": sum(max(len(candidate.aliases) - 1, 0) for candidate in candidates),
            "raw_extraction_checkpoint_count": len(raw_checkpoints),
            "source_aliases": dict(aliases),
            "dropped_contributions": list(dropped),
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
        }
