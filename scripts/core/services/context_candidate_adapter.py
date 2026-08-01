"""Adapt grounded context terms into the existing neologism candidate store."""

from __future__ import annotations

import uuid
from typing import Any, Sequence

from scripts.core.neologism_extraction import (
    AnalysisScope,
    StructuredNeologismExtraction,
)
from scripts.core.neologism_manager import Candidate, ContextEvidence, neologism_manager
from scripts.core.services.context_source_parser import ParsedSourceFile


class ContextCandidateAdapter:
    """Translate structured term output into legacy review candidates."""

    REVIEW_BATCH_SIZE = 20

    def __init__(self, candidate_store: Any = neologism_manager):
        self.candidate_store = candidate_store

    def process_terms(
        self,
        project_id: str,
        parsed_files: Sequence[ParsedSourceFile],
        extractions: Sequence[StructuredNeologismExtraction],
        miner: Any,
        duplicate_index: dict[str, list[dict[str, Any]]],
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
    ) -> dict[str, Any]:
        terms = self._merge_terms(extractions)
        existing = self.candidate_store.load_candidates(project_id)
        existing_keys = {self._term_key(item.original) for item in existing}
        prepared = self._prepare_candidates(terms, parsed_files, duplicate_index, existing_keys)
        reviews = self._review_candidates(
            miner, prepared, source_lang, target_lang, game_name, review_language
        )
        candidates = self._build_candidates(
            project_id, prepared, reviews, source_lang, target_lang, review_language
        )
        latest_keys = {self._term_key(item.original) for item in existing}
        added = [item for item in candidates if self._term_key(item.original) not in latest_keys]
        self.candidate_store.save_candidates(project_id, [*existing, *added])
        return {
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "new_terms": len(added),
            "duplicate_terms": sum(bool(item.duplicate_matches) for item in added),
            "context_release_id": None,
        }

    @classmethod
    def _merge_terms(
        cls,
        extractions: Sequence[StructuredNeologismExtraction],
    ) -> dict[str, dict[str, Any]]:
        terms: dict[str, dict[str, Any]] = {}
        for extraction in extractions:
            for term in extraction.terms:
                key = cls._term_key(term.original)
                current = terms.get(key)
                if current is None or term.confidence > current["confidence"]:
                    terms[key] = term.model_dump()
        return terms

    @staticmethod
    def _term_key(term: str) -> str:
        return " ".join(str(term).casefold().split())

    def _prepare_candidates(
        self,
        terms: dict[str, dict[str, Any]],
        parsed_files: Sequence[ParsedSourceFile],
        duplicate_index: dict[str, list[dict[str, Any]]],
        existing_keys: set[str],
    ) -> list[dict[str, Any]]:
        prepared = []
        for key, term in terms.items():
            if key in existing_keys:
                continue
            evidence = self._term_evidence(term["original"], parsed_files)
            matches = duplicate_index.get(key, [])
            if evidence["context_snippets"]:
                prepared.append({**term, **evidence, "duplicate_matches": matches})
        return prepared

    @staticmethod
    def _term_evidence(
        original: str,
        parsed_files: Sequence[ParsedSourceFile],
    ) -> dict[str, Any]:
        needle = original.casefold()
        snippets: list[str] = []
        source_files: list[str] = []
        context_evidence: list[ContextEvidence] = []
        frequency = 0
        for source_file in parsed_files:
            matched = False
            for item in source_file.items:
                count = item.source_text.casefold().count(needle)
                if not count:
                    continue
                matched = True
                frequency += count
                if item.source_text not in snippets and len(snippets) < 5:
                    snippets.append(item.source_text)
                if len(context_evidence) < 5:
                    context_evidence.append(
                        ContextEvidence(
                            snippet=item.source_text,
                            source_file=str(source_file.path),
                            line=None,
                        )
                    )
            if matched:
                source_files.append(str(source_file.path))
        return {
            "context_snippets": snippets,
            "source_files": source_files,
            "context_evidence": context_evidence,
            "frequency": frequency,
        }

    def _review_candidates(
        self,
        miner: Any,
        prepared: Sequence[dict[str, Any]],
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
    ) -> dict[str, Any]:
        payloads = [
            {
                "original": item["original"],
                "category": item["category"],
                "frequency": item["frequency"],
                "contexts": item["context_snippets"],
            }
            for item in prepared
            if not self._target_suggestion(item["duplicate_matches"], target_lang)
        ]
        reviews: dict[str, Any] = {}
        for offset in range(0, len(payloads), self.REVIEW_BATCH_SIZE):
            reviews.update(
                miner.review_terms(
                    payloads[offset : offset + self.REVIEW_BATCH_SIZE],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    game_name=game_name,
                    review_language=review_language,
                )
            )
        return reviews

    def _build_candidates(
        self,
        project_id: str,
        prepared: Sequence[dict[str, Any]],
        reviews: dict[str, Any],
        source_lang: str,
        target_lang: str,
        review_language: str,
    ) -> list[Candidate]:
        candidates = []
        for item in prepared:
            existing = self._target_suggestion(item["duplicate_matches"], target_lang)
            review = reviews.get(item["original"])
            candidates.append(
                Candidate(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    original=item["original"],
                    context_snippets=item["context_snippets"],
                    suggestion=existing or (review.suggestion if review else ""),
                    reasoning=(
                        "An existing glossary entry matches this source term. Review whether to reuse it, "
                        "create a project override, or mark a new meaning."
                        if existing
                        else review.reasoning
                    ),
                    source_file=item["source_files"][0] if item["source_files"] else None,
                    source_files=item["source_files"],
                    context_evidence=item["context_evidence"],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    review_language=review_language,
                    duplicate_matches=item["duplicate_matches"],
                    frequency=item["frequency"],
                    category=item["category"],
                    confidence=max(item["confidence"], review.confidence if review else 0.0),
                )
            )
        return candidates

    @staticmethod
    def _target_suggestion(matches: list[dict[str, Any]], target_lang: str) -> str:
        for match in matches:
            translations = match.get("translations") or {}
            suggestion = translations.get(target_lang) or translations.get(
                target_lang.replace("-", "_")
            )
            if suggestion:
                return str(suggestion)
        return ""
