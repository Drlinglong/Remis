"""Pure deterministic rules used by context candidate governance."""

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
    _is_english,
    candidate_aggregate_key,
    normalized_match_key,
)


_ARTICLE_RE = re.compile(r"^(?:a|an|the)(?=\s)")
_WORD_OR_HYPHEN = r"[\w-]"


@dataclass(frozen=True)
class CandidateContribution:
    surface: str
    candidate_kind: CandidateKind
    canonical_candidate: str | None
    evidence_source_ids: tuple[str, ...]
    batch_index: int


@dataclass
class CandidateAggregate:
    key: str
    contributions: list[CandidateContribution] = field(default_factory=list)


class ContextCandidateRules:
    """Collect, scan, and classify candidates using backend-owned rules."""

    def collect_aggregates(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        source_lookup: Mapping[str, SourceItem],
        language: str,
    ) -> tuple[
        dict[str, CandidateAggregate],
        dict[int, list[str]],
        list[dict[str, Any]],
    ]:
        aggregates: dict[str, CandidateAggregate] = {}
        keys_by_batch: dict[int, list[str]] = defaultdict(list)
        dropped: list[dict[str, Any]] = []
        for batch_index, extraction in enumerate(extractions):
            for contribution in (*extraction.terms, *extraction.entities):
                item = self.contribution(contribution, batch_index, source_lookup, language)
                if item is None:
                    dropped.append({
                        "batch_index": batch_index,
                        "reason": "empty_normalized_match_key",
                    })
                    continue
                aggregate = aggregates.setdefault(item[0], CandidateAggregate(key=item[0]))
                aggregate.contributions.append(item[1])
                if item[0] not in keys_by_batch[batch_index]:
                    keys_by_batch[batch_index].append(item[0])
        return aggregates, keys_by_batch, dropped

    def contribution(
        self,
        contribution: TermContribution | EntityContribution,
        batch_index: int,
        source_lookup: Mapping[str, SourceItem],
        language: str,
    ) -> tuple[str, CandidateContribution] | None:
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
        return key, CandidateContribution(
            surface=surface,
            candidate_kind=self.candidate_kind(contribution),
            canonical_candidate=contribution.canonical_candidate,
            evidence_source_ids=tuple(dict.fromkeys(evidence_ids)),
            batch_index=batch_index,
        )

    @staticmethod
    def candidate_kind(
        contribution: TermContribution | EntityContribution,
    ) -> CandidateKind:
        if (
            isinstance(contribution, TermContribution)
            and contribution.category in {"person", "place", "faction"}
            and contribution.candidate_kind
            not in {CandidateKind.INCIDENTAL_CONCEPT, CandidateKind.NAMED_PHRASE}
        ):
            # These categories identify recurring narrative referents rather
            # than mechanics.  Models sometimes label roles such as Knight or
            # Squire as glossary terms despite the entity contract.
            return CandidateKind.ENTITY
        if contribution.candidate_kind is not None:
            return CandidateKind(contribution.candidate_kind)
        if isinstance(contribution, EntityContribution):
            return CandidateKind.ENTITY
        return CandidateKind.GLOSSARY_TERM

    @staticmethod
    def unit_indexes(
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
    def final_chain_index(
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

    def build_candidate(
        self,
        aggregate: CandidateAggregate,
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
        evidence_ids = self.ordered_evidence_ids(
            aggregate, items, source_lookup, language
        )
        mention_count, scanned_ids = self.scan_aliases(aggregate, items, language)
        source_ids = self.ordered_ids(items, (*scanned_ids, *evidence_ids))
        mention_count += len(set(evidence_ids) - set(scanned_ids))
        local_ids = self.ordered_local_ids(source_ids, unit_by_source, source_ids_by_unit)
        event_ids = self.ordered_event_ids(local_ids, chain_by_unit)
        has_unit_mapping = any(source_id in unit_by_source for source_id in source_ids)
        policy_coverage = len(local_ids) if has_unit_mapping else len(source_ids)
        match_key = self.match_key(aggregate.key)
        kind = self.resolved_kind(aggregate, overrides, language)
        override = self.override_for(overrides, match_key, language)
        reasons = self.promotion_reasons(match_key, glossary_keys, confirmed_keys, override)
        tier = self.tier(policy_coverage, len(event_ids), kind, reasons, override)
        summary_eligible = self.summary_eligible(kind, tier, override)
        glossary_eligible = self.glossary_eligible(kind, tier, override, reasons)
        audit_only = self.audit_only(kind, override, reasons)
        suggestions = self.suggestions(aggregate)
        semantic_suggestions = tuple(
            suggestion
            for suggestion in suggestions
            if normalized_match_key(suggestion, language) != match_key
        )
        return ContextCandidate(
            aggregate_key=aggregate.key,
            normalized_match_key=match_key,
            canonical_display_name=self.canonical_display_name(aggregate),
            canonical_candidate=suggestions[0] if suggestions else None,
            canonical_suggestions=suggestions,
            semantic_canonical_suggestions=semantic_suggestions,
            aliases=self.literal_aliases(aggregate),
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

    def ordered_evidence_ids(
        self,
        aggregate: CandidateAggregate,
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
        aliases = self.scan_aliases_for_aggregate(aggregate, language)
        grounded = {
            item.source_item_id
            for item in items
            if item.source_item_id in supplied
            and self.non_overlapping_alias_matches(item.source_text, aliases)
        }
        return tuple(item.source_item_id for item in items if item.source_item_id in grounded)

    def scan_aliases(
        self,
        aggregate: CandidateAggregate,
        items: Sequence[SourceItem],
        language: str,
    ) -> tuple[int, tuple[str, ...]]:
        aliases = self.scan_aliases_for_aggregate(aggregate, language)
        count = 0
        source_ids: list[str] = []
        for item in items:
            matches = self.non_overlapping_alias_matches(item.source_text, aliases)
            if matches:
                count += len(matches)
                source_ids.append(item.source_item_id)
        return count, tuple(source_ids)

    @staticmethod
    def scan_aliases_for_aggregate(
        aggregate: CandidateAggregate,
        language: str,
    ) -> tuple[str, ...]:
        aliases: list[str] = []
        for contribution in aggregate.contributions:
            cleaned = scan_surface(contribution.surface)
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned)
            if _is_english(language):
                article_free = remove_leading_article(cleaned)
                if article_free and article_free not in aliases:
                    aliases.append(article_free)
        return tuple(aliases)

    @staticmethod
    def non_overlapping_alias_matches(
        text: str,
        aliases: Sequence[str],
    ) -> list[tuple[int, int]]:
        normalized_text = _scan_text(text)
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
            matches.extend(
                (match.start(), match.end())
                for match in re.finditer(pattern, normalized_text)
            )
        selected: list[tuple[int, int]] = []
        for start, end in sorted(matches, key=lambda span: (span[0], -(span[1] - span[0]))):
            if not any(start < selected_end and end > selected_start for selected_start, selected_end in selected):
                selected.append((start, end))
        return selected

    @staticmethod
    def ordered_ids(
        items: Sequence[SourceItem],
        source_ids: Iterable[str],
    ) -> tuple[str, ...]:
        selected = set(source_ids)
        return tuple(item.source_item_id for item in items if item.source_item_id in selected)

    @staticmethod
    def ordered_local_ids(
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
    def ordered_event_ids(
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
    def canonical_display_name(aggregate: CandidateAggregate) -> str:
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
    def literal_aliases(aggregate: CandidateAggregate) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.surface for item in aggregate.contributions))

    @staticmethod
    def suggestions(aggregate: CandidateAggregate) -> tuple[str, ...]:
        return tuple(dict.fromkeys(
            item.canonical_candidate
            for item in aggregate.contributions
            if item.canonical_candidate
        ))

    def resolved_kind(
        self,
        aggregate: CandidateAggregate,
        overrides: Mapping[str, Any],
        language: str,
    ) -> CandidateKind:
        override = self.override_for(overrides, self.match_key(aggregate.key), language)
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
    def promotion_reasons(
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
    def tier(
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
    def summary_eligible(
        kind: CandidateKind,
        tier: CandidateTier,
        override: Mapping[str, Any],
    ) -> bool:
        if override.get("summary_eligible") is not None:
            return bool(override["summary_eligible"])
        return (
            tier in {CandidateTier.CORE, CandidateTier.SECONDARY}
            and kind is CandidateKind.ENTITY
        )

    @staticmethod
    def glossary_eligible(
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
    def audit_only(
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
    def policy_for(candidate: ContextCandidate) -> CandidatePolicy:
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

    def normalized_key_set(
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
            raw = self.match_key(self.value_surface(value))
            key = normalized_match_key(raw, language)
            if key:
                result.add(key)
        return result

    @staticmethod
    def as_values(value: Iterable[Any] | None) -> tuple[Any, ...]:
        if value is None:
            return ()
        if isinstance(value, (str, bytes)):
            return (value,)
        if isinstance(value, Mapping) and any(
            name in value
            for name in (
                "normalized_match_key",
                "aggregate_key",
                "original",
                "name",
                "surface",
                "match_key",
            )
        ):
            return (value,)
        return tuple(value)

    @staticmethod
    def value_surface(value: Any) -> str:
        names = (
            "normalized_match_key",
            "aggregate_key",
            "original",
            "name",
            "surface",
            "match_key",
        )
        if isinstance(value, Mapping):
            for name in names:
                if value.get(name):
                    return str(value[name])
        for name in names:
            nested = getattr(value, name, None)
            if nested:
                return str(nested)
        return str(value)

    def override_for(
        self,
        overrides: Mapping[str, Any],
        match_key: str,
        language: str,
    ) -> Mapping[str, Any]:
        for raw_key, raw_value in overrides.items():
            key = normalized_match_key(self.match_key(str(raw_key)), language)
            if key == match_key:
                if raw_value is True:
                    return {"promote_to_core": True}
                if isinstance(raw_value, str):
                    return {"tier": raw_value}
                if isinstance(raw_value, Mapping):
                    return raw_value
        return {}

    @staticmethod
    def match_key(value: str) -> str:
        raw = str(value)
        for prefix in ("candidate:", "entity:"):
            if raw.casefold().startswith(prefix):
                return raw[len(prefix):]
        return raw

    def override_flag(
        self,
        overrides: Mapping[str, Any],
        aggregate_key: str,
        language: str,
        flag: str,
    ) -> bool:
        return bool(self.override_for(overrides, aggregate_key, language).get(flag))


def scan_surface(surface: str) -> str:
    return normalized_match_key(surface, "und")


def _scan_text(value: str) -> str:
    """Normalize source prose while exposing Paradox display references."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"§[0-9a-z]", "", normalized)
    return re.sub(r"[\[\]$_.:/]+", " ", normalized)


def remove_leading_article(value: str) -> str:
    return _ARTICLE_RE.sub("", value, count=1).strip()
