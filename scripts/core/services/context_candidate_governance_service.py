"""Deterministic governance for source-grounded Mod Context candidates."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from scripts.core.context_local_units import DeliveryAssignment, LocalTextUnit
from scripts.core.neologism_extraction import (
    EntityContribution,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.schemas.context_candidate import (
    CandidateKind,
    CandidatePolicy,
    CandidateTier,
    ContextCandidate,
    ContextCandidateGovernanceResult,
    _is_english,
    candidate_aggregate_key,
    normalized_match_key,
)


_ARTICLE_RE = re.compile(r"^(?:a|an|the)(?=\s)")
_WORD_OR_HYPHEN = r"[\w-]"


@dataclass(frozen=True)
class _Contribution:
    surface: str
    candidate_kind: CandidateKind
    canonical_candidate: str | None
    evidence_source_ids: tuple[str, ...]
    batch_index: int


@dataclass
class _Aggregate:
    key: str
    contributions: list[_Contribution] = field(default_factory=list)


class ContextCandidateGovernanceService:
    """Merge literal aliases, compute coverage, and apply review policy."""

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
        aggregates, keys_by_batch, dropped = self._collect_aggregates(
            extractions, source_lookup, language
        )
        unit_by_source, source_ids_by_unit = self._unit_indexes(units)
        chain_by_unit = self._final_chain_index(assignments)
        glossary_keys = self._normalized_key_set(
            (
                *self._as_values(existing_glossary_matches),
                *self._as_values(existing_glossary_match_keys),
                *self._as_values(glossary_match_keys),
                *self._as_values(glossary_matches),
            ),
            language,
        )
        confirmed_keys = self._normalized_key_set(user_confirmed_match_keys, language)
        overrides = {
            **(user_overrides or {}),
            **(user_policy_overrides or {}),
        }
        candidates = tuple(
            self._build_candidate(
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
            candidate.aggregate_key: self._policy_for(candidate)
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
            if candidate.summary_eligible or self._override_flag(
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

    def _collect_aggregates(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        source_lookup: Mapping[str, SourceItem],
        language: str,
    ) -> tuple[dict[str, _Aggregate], dict[int, list[str]], list[dict[str, Any]]]:
        aggregates: dict[str, _Aggregate] = {}
        keys_by_batch: dict[int, list[str]] = defaultdict(list)
        dropped: list[dict[str, Any]] = []
        for batch_index, extraction in enumerate(extractions):
            for contribution in (*extraction.terms, *extraction.entities):
                item = self._contribution(contribution, batch_index, source_lookup, language)
                if item is None:
                    dropped.append({
                        "batch_index": batch_index,
                        "reason": "empty_normalized_match_key",
                    })
                    continue
                aggregate = aggregates.setdefault(item[0], _Aggregate(key=item[0]))
                aggregate.contributions.append(item[1])
                if item[0] not in keys_by_batch[batch_index]:
                    keys_by_batch[batch_index].append(item[0])
        return aggregates, keys_by_batch, dropped

    def _contribution(
        self,
        contribution: TermContribution | EntityContribution,
        batch_index: int,
        source_lookup: Mapping[str, SourceItem],
        language: str,
    ) -> tuple[str, _Contribution] | None:
        surface = contribution.original if isinstance(contribution, TermContribution) else contribution.name
        match_key = normalized_match_key(surface, language)
        if not match_key:
            return None
        key = candidate_aggregate_key(surface, language)
        evidence_ids = tuple(
            evidence.source_item_id
            for evidence in contribution.evidence
            if evidence.source_item_id in source_lookup
        )
        kind = self._candidate_kind(contribution)
        return key, _Contribution(
            surface=surface,
            candidate_kind=kind,
            canonical_candidate=contribution.canonical_candidate,
            evidence_source_ids=tuple(dict.fromkeys(evidence_ids)),
            batch_index=batch_index,
        )

    @staticmethod
    def _candidate_kind(
        contribution: TermContribution | EntityContribution,
    ) -> CandidateKind:
        if contribution.candidate_kind is not None:
            return CandidateKind(contribution.candidate_kind)
        if isinstance(contribution, EntityContribution):
            return CandidateKind.ENTITY
        return CandidateKind.GLOSSARY_TERM

    @staticmethod
    def _unit_indexes(
        units: Sequence[LocalTextUnit],
    ) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
        unit_by_source: dict[str, list[str]] = defaultdict(list)
        source_ids_by_unit: dict[str, tuple[str, ...]] = {}
        for unit in units:
            source_ids = tuple(str(item.source_item_id) for item in unit.items)
            source_ids_by_unit[unit.unit_id] = source_ids
            for source_id in source_ids:
                unit_by_source[source_id].append(unit.unit_id)
        return (
            {source_id: tuple(unit_ids) for source_id, unit_ids in unit_by_source.items()},
            source_ids_by_unit,
        )

    @staticmethod
    def _final_chain_index(
        assignments: Sequence[DeliveryAssignment],
    ) -> dict[str, tuple[str, ...]]:
        chains_by_unit: dict[str, list[str]] = defaultdict(list)
        for assignment in assignments:
            if assignment.assignment_state != "assigned":
                continue
            for link in assignment.links:
                if link.relation == "theme_related":
                    continue
                if link.event_chain_id.casefold() not in {
                    chain.casefold() for chain in chains_by_unit[assignment.local_unit_id]
                }:
                    chains_by_unit[assignment.local_unit_id].append(link.event_chain_id)
        return {
            unit_id: tuple(chain_ids)
            for unit_id, chain_ids in chains_by_unit.items()
        }

    def _build_candidate(
        self,
        aggregate: _Aggregate,
        items: Sequence[SourceItem],
        source_lookup: Mapping[str, SourceItem],
        unit_by_source: Mapping[str, tuple[str, ...]],
        source_ids_by_unit: Mapping[str, tuple[str, ...]],
        chain_by_unit: Mapping[str, tuple[str, ...]],
        glossary_keys: set[str],
        confirmed_keys: set[str],
        overrides: Mapping[str, Any],
        language: str,
    ) -> ContextCandidate:
        evidence_ids = self._ordered_evidence_ids(
            aggregate, items, source_lookup, language
        )
        mention_count, scanned_ids = self._scan_aliases(aggregate, items, language)
        source_ids = self._ordered_ids(items, (*scanned_ids, *evidence_ids))
        mention_count += len(set(evidence_ids) - set(scanned_ids))
        local_ids = self._ordered_local_ids(source_ids, unit_by_source, source_ids_by_unit)
        event_ids = self._ordered_event_ids(local_ids, chain_by_unit)
        has_unit_mapping = any(source_id in unit_by_source for source_id in source_ids)
        policy_coverage = len(local_ids) if has_unit_mapping else len(source_ids)
        match_key = self._match_key(aggregate.key)
        kind = self._resolved_kind(aggregate, overrides, language)
        override = self._override_for(overrides, match_key, language)
        reasons = self._promotion_reasons(match_key, glossary_keys, confirmed_keys, override)
        tier = self._tier(policy_coverage, len(event_ids), kind, reasons, override)
        summary_eligible = self._summary_eligible(kind, tier, override)
        glossary_eligible = self._glossary_eligible(kind, tier, override, reasons)
        audit_only = self._audit_only(kind, override, reasons)
        suggestions = self._suggestions(aggregate)
        semantic_suggestions = tuple(
            suggestion
            for suggestion in suggestions
            if normalized_match_key(suggestion, language) != match_key
        )
        return ContextCandidate(
            aggregate_key=aggregate.key,
            normalized_match_key=match_key,
            canonical_display_name=self._canonical_display_name(aggregate),
            canonical_candidate=suggestions[0] if suggestions else None,
            canonical_suggestions=suggestions,
            semantic_canonical_suggestions=semantic_suggestions,
            aliases=self._literal_aliases(aggregate),
            candidate_kind=kind,
            mention_count=mention_count,
            source_item_coverage=len(source_ids),
            local_unit_coverage=len(local_ids),
            event_chain_coverage=len(event_ids),
            policy_coverage=policy_coverage,
            tier=tier,
            source_item_ids=source_ids,
            local_unit_ids=local_ids,
            event_chain_ids=event_ids,
            promotion_reasons=reasons,
            summary_eligible=summary_eligible,
            glossary_eligible=glossary_eligible,
            audit_only=audit_only,
        )

    def _ordered_evidence_ids(
        self,
        aggregate: _Aggregate,
        items: Sequence[SourceItem],
        source_lookup: Mapping[str, SourceItem],
        language: str,
    ) -> tuple[str, ...]:
        supplied = {
            source_id
            for contribution in aggregate.contributions
            for source_id in contribution.evidence_source_ids
            if source_id in source_lookup
        }
        aliases = self._scan_aliases_for_aggregate(aggregate, language)
        grounded = {
            item.source_item_id
            for item in items
            if item.source_item_id in supplied
            and self._non_overlapping_alias_matches(item.source_text, aliases)
        }
        return tuple(item.source_item_id for item in items if item.source_item_id in grounded)

    def _scan_aliases(
        self,
        aggregate: _Aggregate,
        items: Sequence[SourceItem],
        language: str,
    ) -> tuple[int, tuple[str, ...]]:
        aliases = self._scan_aliases_for_aggregate(aggregate, language)
        count = 0
        source_ids: list[str] = []
        for item in items:
            matches = self._non_overlapping_alias_matches(item.source_text, aliases)
            if matches:
                count += len(matches)
                source_ids.append(item.source_item_id)
        return count, tuple(source_ids)

    @staticmethod
    def _scan_aliases_for_aggregate(
        aggregate: _Aggregate,
        language: str,
    ) -> tuple[str, ...]:
        aliases: list[str] = []
        for contribution in aggregate.contributions:
            cleaned = _scan_surface(contribution.surface)
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned)
            if _is_english(language):
                article_free = _remove_leading_article(cleaned)
                if article_free and article_free not in aliases:
                    aliases.append(article_free)
        return tuple(aliases)

    @staticmethod
    def _non_overlapping_alias_matches(text: str, aliases: Sequence[str]) -> list[tuple[int, int]]:
        normalized_text = unicodedata.normalize("NFKC", text).casefold()
        matches: list[tuple[int, int]] = []
        for alias in aliases:
            tokens = [token for token in re.split(r"\s+", alias) if token]
            if not tokens:
                continue
            pattern = (
                rf"(?<!{_WORD_OR_HYPHEN})"
                + r"\s+".join(re.escape(token) for token in tokens)
                + rf"(?!{_WORD_OR_HYPHEN})"
            )
            matches.extend((match.start(), match.end()) for match in re.finditer(pattern, normalized_text))
        selected: list[tuple[int, int]] = []
        for start, end in sorted(matches, key=lambda span: (span[0], -(span[1] - span[0]))):
            if not any(start < selected_end and end > selected_start for selected_start, selected_end in selected):
                selected.append((start, end))
        return selected

    @staticmethod
    def _ordered_ids(
        items: Sequence[SourceItem],
        source_ids: Iterable[str],
    ) -> tuple[str, ...]:
        selected = set(source_ids)
        return tuple(item.source_item_id for item in items if item.source_item_id in selected)

    @staticmethod
    def _ordered_local_ids(
        source_ids: Sequence[str],
        unit_by_source: Mapping[str, tuple[str, ...]],
        source_ids_by_unit: Mapping[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        selected = {
            unit_id
            for source_id in source_ids
            for unit_id in unit_by_source.get(source_id, ())
        }
        return tuple(unit_id for unit_id in source_ids_by_unit if unit_id in selected)

    @staticmethod
    def _ordered_event_ids(
        local_ids: Sequence[str],
        chain_by_unit: Mapping[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        for unit_id in local_ids:
            for chain_id in chain_by_unit.get(unit_id, ()):
                key = chain_id.casefold()
                if key not in seen:
                    seen.add(key)
                    result.append(chain_id)
        return tuple(result)

    @staticmethod
    def _canonical_display_name(aggregate: _Aggregate) -> str:
        counts = Counter(item.surface for item in aggregate.contributions)
        surfaces = list(counts)
        return min(
            surfaces,
            key=lambda surface: (
                int(bool(re.match(r"^(?:a|an|the)\s", surface, flags=re.IGNORECASE))),
                -counts[surface],
                surface.casefold(),
                surface,
            ),
        )

    @staticmethod
    def _literal_aliases(aggregate: _Aggregate) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.surface for item in aggregate.contributions))

    @staticmethod
    def _suggestions(aggregate: _Aggregate) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            item.canonical_candidate
            for item in aggregate.contributions
            if item.canonical_candidate
        ))

    def _resolved_kind(
        self,
        aggregate: _Aggregate,
        overrides: Mapping[str, Any],
        language: str,
    ) -> CandidateKind:
        override = self._override_for(overrides, self._match_key(aggregate.key), language)
        if override.get("candidate_kind"):
            try:
                return CandidateKind(override["candidate_kind"])
            except ValueError:
                pass
        priority = {
            CandidateKind.INCIDENTAL_CONCEPT: 0,
            CandidateKind.GLOSSARY_TERM: 1,
            CandidateKind.NAMED_PHRASE: 2,
            CandidateKind.ENTITY: 3,
        }
        return max(
            (item.candidate_kind for item in aggregate.contributions),
            key=lambda kind: priority[kind],
        )

    @staticmethod
    def _promotion_reasons(
        aggregate_key: str,
        glossary_keys: set[str],
        confirmed_keys: set[str],
        override: Mapping[str, Any],
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if aggregate_key in glossary_keys:
            reasons.append("existing_glossary_match")
        if aggregate_key in confirmed_keys or override.get("user_confirmed"):
            reasons.append("user_confirmed")
        if override.get("promote_to_core") or override.get("promote"):
            reasons.append("user_policy_override")
        if any(
            name in override
            for name in (
                "candidate_kind",
                "tier",
                "summary_eligible",
                "glossary_eligible",
                "audit_only",
            )
        ):
            reasons.append("user_policy_override")
        if override.get("audit_only") is True:
            reasons.append("user_policy_audit_only")
        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _tier(
        policy_coverage: int,
        event_coverage: int,
        kind: CandidateKind,
        reasons: Sequence[str],
        override: Mapping[str, Any],
    ) -> CandidateTier:
        if "existing_glossary_match" in reasons or "user_confirmed" in reasons:
            tier = CandidateTier.CORE
        elif event_coverage >= 2 or policy_coverage >= 3:
            tier = CandidateTier.CORE
        elif policy_coverage >= 2:
            tier = CandidateTier.SECONDARY
        elif policy_coverage == 1 and kind is not CandidateKind.INCIDENTAL_CONCEPT:
            tier = CandidateTier.SECONDARY
        else:
            tier = CandidateTier.INCIDENTAL
        if override.get("promote_to_core") or override.get("promote"):
            tier = CandidateTier.CORE
        requested = override.get("tier")
        if requested in {CandidateTier.CORE.value, CandidateTier.CORE}:
            tier = CandidateTier.CORE
        elif requested in {CandidateTier.SECONDARY.value, CandidateTier.SECONDARY} and tier is CandidateTier.INCIDENTAL:
            tier = CandidateTier.SECONDARY
        return tier

    @staticmethod
    def _summary_eligible(
        kind: CandidateKind,
        tier: CandidateTier,
        override: Mapping[str, Any],
    ) -> bool:
        if override.get("summary_eligible") is not None:
            return bool(override["summary_eligible"])
        return tier is CandidateTier.CORE and kind is CandidateKind.ENTITY

    @staticmethod
    def _glossary_eligible(
        kind: CandidateKind,
        tier: CandidateTier,
        override: Mapping[str, Any],
        reasons: Sequence[str],
    ) -> bool:
        if override.get("glossary_eligible") is not None:
            return bool(override["glossary_eligible"])
        if {"user_confirmed", "existing_glossary_match"} & set(reasons):
            return True
        return tier in {CandidateTier.CORE, CandidateTier.SECONDARY} and kind is not CandidateKind.INCIDENTAL_CONCEPT

    @staticmethod
    def _audit_only(
        kind: CandidateKind,
        override: Mapping[str, Any],
        reasons: Sequence[str],
    ) -> bool:
        if override.get("audit_only") is not None:
            return bool(override["audit_only"])
        if {"user_confirmed", "existing_glossary_match"} & set(reasons):
            return False
        return kind is CandidateKind.INCIDENTAL_CONCEPT

    @staticmethod
    def _policy_for(candidate: ContextCandidate) -> CandidatePolicy:
        return CandidatePolicy(
            aggregate_key=candidate.aggregate_key,
            candidate_kind=candidate.candidate_kind,
            tier=candidate.tier,
            policy_coverage=candidate.policy_coverage,
            event_chain_coverage=candidate.event_chain_coverage,
            summary_eligible=candidate.summary_eligible,
            glossary_eligible=candidate.glossary_eligible,
            audit_only=candidate.audit_only,
            promotion_reasons=candidate.promotion_reasons,
        )

    def _normalized_key_set(
        self,
        values: Iterable[Any],
        language: str,
    ) -> set[str]:
        if values is None:
            return set()
        if isinstance(values, (str, bytes)):
            values = (values,)
        result: set[str] = set()
        for value in values:
            raw = self._match_key(self._value_surface(value))
            key = normalized_match_key(raw, language)
            if key:
                result.add(key)
        return result

    @staticmethod
    def _as_values(value: Iterable[Any] | None) -> tuple[Any, ...]:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)):
            return (value,)
        if isinstance(value, Mapping) and any(
            name in value
            for name in ("normalized_match_key", "aggregate_key", "original", "name", "surface", "match_key")
        ):
            return (value,)
        return tuple(value)

    @staticmethod
    def _value_surface(value: Any) -> str:
        if isinstance(value, Mapping):
            for name in (
                "normalized_match_key",
                "aggregate_key",
                "original",
                "name",
                "surface",
                "match_key",
            ):
                if value.get(name):
                    return str(value[name])
        for name in (
            "normalized_match_key",
            "aggregate_key",
            "original",
            "name",
            "surface",
            "match_key",
        ):
            nested = getattr(value, name, None)
            if nested:
                return str(nested)
        return str(value)

    def _override_for(
        self,
        overrides: Mapping[str, Any],
        match_key: str,
        language: str,
    ) -> Mapping[str, Any]:
        for raw_key, raw_value in overrides.items():
            key = normalized_match_key(self._match_key(str(raw_key)), language)
            if key == match_key:
                if raw_value is True:
                    return {"promote_to_core": True}
                if isinstance(raw_value, str):
                    return {"tier": raw_value}
                if isinstance(raw_value, Mapping):
                    return raw_value
        return {}

    @staticmethod
    def _match_key(value: str) -> str:
        raw = str(value)
        for prefix in ("candidate:", "entity:"):
            if raw.casefold().startswith(prefix):
                return raw[len(prefix):]
        return raw

    def _override_flag(
        self,
        overrides: Mapping[str, Any],
        aggregate_key: str,
        language: str,
        flag: str,
    ) -> bool:
        return bool(self._override_for(overrides, aggregate_key, language).get(flag))

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


def _scan_surface(surface: str) -> str:
    return normalized_match_key(surface, "und")


def _remove_leading_article(value: str) -> str:
    return _ARTICLE_RE.sub("", value, count=1).strip()
