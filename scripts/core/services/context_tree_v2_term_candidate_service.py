"""Persist program-governed v2 term variants without a second review model call."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any, Mapping, Sequence

from scripts.core.neologism_manager import Candidate, ContextEvidence
from scripts.schemas.context_candidate import normalized_match_key


class ContextTreeV2TermCandidateService:
    """Bridge the v2 term result into the existing human review court."""

    def __init__(self, candidate_store: Any, *, source_language: str = "en") -> None:
        self.candidate_store = candidate_store
        self.source_language = source_language

    def persist(
        self,
        project_id: str,
        term_result: Any,
        governance: Any | None,
        source_items: Sequence[Any],
        *,
        local_units: Sequence[Any] = (),
        target_language: str,
        review_language: str,
        duplicate_index: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    ) -> dict[str, int]:
        item_lookup = {item.source_item_id: item for item in source_items}
        source_to_units = self._source_to_units(local_units)
        governed = {
            key: item
            for item in getattr(governance, "candidates", ())
            for key in self._candidate_keys(item)
        }
        incoming = [
            self._candidate(
                project_id,
                term,
                governed.get(term.normalized_key),
                item_lookup,
                source_to_units,
                target_language,
                review_language,
                duplicate_index or {},
            )
            for term in term_result.terms
        ]
        incoming = [item for item in incoming if item is not None]
        lock_factory = getattr(self.candidate_store, "_candidate_lock", None)
        lock = lock_factory(project_id) if callable(lock_factory) else nullcontext()
        with lock:
            existing = self.candidate_store.load_candidates(project_id)
            by_key = {
                normalized_match_key(item.original, self.source_language): item
                for item in existing
            }
            added = 0
            duplicates = 0
            for candidate in incoming:
                key = normalized_match_key(candidate.original, self.source_language)
                current = by_key.get(key)
                if current is None:
                    existing.append(candidate)
                    by_key[key] = candidate
                    added += 1
                else:
                    duplicates += 1
                    if current.status == "pending":
                        self._refresh_pending(current, candidate)
            self.candidate_store.save_candidates(project_id, existing)
        return {"new_terms": added, "duplicate_terms": duplicates}

    def _candidate_keys(self, candidate: Any) -> tuple[str, ...]:
        values = [candidate.canonical_name, *getattr(candidate, "aliases", ())]
        return tuple(dict.fromkeys(
            normalized_match_key(value, self.source_language)
            for value in values if str(value).strip()
        ))

    @staticmethod
    def _source_to_units(local_units: Sequence[Any]) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        for unit in local_units:
            for item in unit.items:
                result.setdefault(item.source_item_id, []).append(unit.unit_id)
        return {key: tuple(dict.fromkeys(value)) for key, value in result.items()}

    @staticmethod
    def _refresh_pending(current: Candidate, incoming: Candidate) -> None:
        for field in (
            "context_snippets", "context_evidence", "source_file", "source_files",
            "suggestion", "reasoning", "frequency", "confidence", "tier",
            "local_unit_coverage", "mention_count", "suggestion_variants",
        ):
            setattr(current, field, getattr(incoming, field))

    def _candidate(
        self,
        project_id: str,
        term: Any,
        governed: Any | None,
        item_lookup: Mapping[str, Any],
        source_to_units: Mapping[str, Sequence[str]],
        target_language: str,
        review_language: str,
        duplicate_index: Mapping[str, Sequence[Mapping[str, Any]]],
    ) -> Candidate | None:
        evidence_ids = tuple(dict.fromkeys(
            evidence.source_item_id
            for variant in term.variants
            for evidence in variant.evidence
            if evidence.source_item_id in item_lookup
        ))
        if not evidence_ids:
            return None
        items = [item_lookup[item_id] for item_id in evidence_ids]
        variants = [variant.model_dump(mode="json") for variant in term.variants]
        first = term.variants[0]
        fallback_units = tuple(dict.fromkeys(
            unit_id for evidence_id in evidence_ids
            for unit_id in source_to_units.get(evidence_id, ())
        ))
        coverage = int(getattr(governed, "local_unit_coverage", len(fallback_units)))
        fallback_grade = "A" if coverage >= 3 else ("B" if coverage == 2 else "C")
        grade = str(getattr(getattr(governed, "grade", None), "value", fallback_grade))
        mention_count = int(getattr(governed, "mention_count", len(term.variants)))
        duplicate_matches = list(duplicate_index.get(term.normalized_key, ()))
        candidate_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"remis:term:{project_id}:{term.normalized_key}",
        ))
        return Candidate(
            id=candidate_id,
            project_id=project_id,
            original=term.original,
            context_snippets=list(dict.fromkeys(item.source_text for item in items)),
            context_evidence=[
                ContextEvidence(snippet=item.source_text, source_file=item.relative_path)
                for item in items
            ],
            source_file=items[0].relative_path,
            source_files=list(dict.fromkeys(item.relative_path for item in items)),
            suggestion=first.suggestion or "",
            reasoning=first.reasoning or "",
            source_lang=self.source_language,
            target_lang=target_language,
            review_language=review_language,
            duplicate_matches=duplicate_matches,
            frequency=max(mention_count, 1),
            confidence=1.0 if first.suggestion and first.reasoning else 0.5,
            tier=grade if grade in {"A", "B", "C"} else "C",
            local_unit_coverage=coverage,
            mention_count=mention_count,
            suggestion_variants=variants,
        )


__all__ = ["ContextTreeV2TermCandidateService"]
