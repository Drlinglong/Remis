"""Adapt grounded context terms into the existing neologism candidate store."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceItem,
    TermContribution,
    StructuredNeologismExtraction,
)
from scripts.core.neologism_manager import Candidate, ContextEvidence, neologism_manager
from scripts.core.services.context_source_parser import ContextSourceParser, ParsedSourceFile


class ContextCandidateAdapter:
    """Translate structured term output into legacy review candidates."""

    REVIEW_BATCH_SIZE = 20

    def __init__(self, candidate_store: Any = neologism_manager, batch_store: Any | None = None):
        self.candidate_store = candidate_store
        self.batch_store = batch_store

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
        *,
        task_id: str | None = None,
        source_snapshot_hash: str | None = None,
        analysis_scope: Mapping[str, Any] | AnalysisScope | None = None,
        analysis_config: Mapping[str, Any] | None = None,
        run_id: str | None = None,
        batch_store: Any | None = None,
    ) -> dict[str, Any]:
        checkpoint_store = batch_store or self.batch_store
        run = self._start_run(
            checkpoint_store,
            project_id,
            task_id,
            source_snapshot_hash,
            parsed_files,
            analysis_scope,
            analysis_config,
            source_lang,
            target_lang,
            game_name,
            review_language,
            run_id,
        )
        terms, rejected = self._collect_terms(extractions)
        self._save_extraction_batches(checkpoint_store, run, extractions, parsed_files, rejected)
        existing = self.candidate_store.load_candidates(project_id)
        existing_keys = {self._term_key(item.original) for item in existing}
        prepared = self._prepare_candidates(terms, parsed_files, duplicate_index, existing_keys, rejected)
        reviews = self._review_candidates(
            miner, prepared, source_lang, target_lang, game_name, review_language, checkpoint_store, run
        )
        candidates = self._build_candidates(
            project_id, prepared, reviews, source_lang, target_lang, review_language
        )
        latest_keys = {self._term_key(item.original) for item in existing}
        added = [item for item in candidates if self._term_key(item.original) not in latest_keys]
        self.candidate_store.save_candidates(project_id, [*existing, *added])
        if checkpoint_store is not None and run is not None:
            checkpoint_store.mark_analysis_ready(run.run_id)
        return {
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "new_terms": len(added),
            "duplicate_terms": sum(bool(item.duplicate_matches) for item in added),
            "context_release_id": None,
            "run_id": run.run_id if run is not None else None,
            "rejected_terms": rejected,
        }

    @staticmethod
    def _start_run(
        checkpoint_store: Any | None,
        project_id: str,
        task_id: str | None,
        source_snapshot_hash: str | None,
        parsed_files: Sequence[ParsedSourceFile],
        analysis_scope: Mapping[str, Any] | AnalysisScope | None,
        analysis_config: Mapping[str, Any] | None,
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
        run_id: str | None,
    ) -> Any | None:
        if checkpoint_store is None:
            return None
        snapshot = ContextSourceParser.build_snapshot(parsed_files)
        scope = analysis_scope
        if isinstance(scope, AnalysisScope):
            scope = {"mode": scope.value}
        scope = dict(scope or {"mode": AnalysisScope.TERMS_ONLY.value})
        config = {
            "source_lang": source_lang,
            "target_lang": target_lang,
            "game_name": game_name,
            "review_language": review_language,
            **dict(analysis_config or {}),
        }
        return checkpoint_store.start_or_resume_run(
            project_id,
            task_id,
            source_snapshot_hash or snapshot.source_snapshot_hash,
            scope,
            config,
            run_id=run_id,
        )

    def _save_extraction_batches(
        self,
        checkpoint_store: Any | None,
        run: Any | None,
        extractions: Sequence[StructuredNeologismExtraction],
        parsed_files: Sequence[ParsedSourceFile],
        rejected: list[dict[str, Any]],
    ) -> None:
        if checkpoint_store is None or run is None:
            return
        source_lookup = {
            item.source_item_id: item
            for source_file in parsed_files
            for item in source_file.items
        }
        source_items = set(source_lookup)
        for index, extraction in enumerate(extractions):
            terms = []
            source_ids: list[str] = []
            for raw_term in getattr(extraction, "terms", ()):
                try:
                    term = self._validated_term(raw_term)
                except ValidationError:
                    continue
                data = {key: value for key, value in self._term_data(term, raw_term).items() if key != "_batch_index"}
                data["source_references"] = [
                    {
                        "source_item_id": entry.get("source_item_id"),
                        "relative_path": source_lookup[entry["source_item_id"]].relative_path
                        if entry.get("source_item_id") in source_lookup else entry.get("relative_path", ""),
                        "item_key": source_lookup[entry["source_item_id"]].item_key
                        if entry.get("source_item_id") in source_lookup else entry.get("item_key"),
                        "source_order": source_lookup[entry["source_item_id"]].source_order
                        if entry.get("source_item_id") in source_lookup else entry.get("source_order"),
                    }
                    for entry in data.get("evidence", [])
                ]
                terms.append(data)
                source_ids.extend(
                    evidence["source_item_id"]
                    for evidence in data.get("evidence", [])
                    if evidence.get("source_item_id") in source_items
                )
            source_rows = [
                {
                    "source_item_id": source_lookup[source_id].source_item_id,
                    "relative_path": source_lookup[source_id].relative_path,
                    "item_key": source_lookup[source_id].item_key,
                    "source_order": source_lookup[source_id].source_order,
                    "source_text": source_lookup[source_id].source_text,
                }
                for source_id in dict.fromkeys(source_ids)
                if source_id in source_lookup
            ]
            batch_rejected = [item for item in rejected if item.get("batch_index") == index]
            checkpoint_store.save_batch(
                run.run_id,
                "extraction",
                index,
                source_ids,
                {"terms": terms, "source_items": source_rows, "rejected": batch_rejected},
            )

    @staticmethod
    def rebuild_source_items(payload: Mapping[str, Any]) -> tuple[SourceItem, ...]:
        """Rebuild model inputs from persisted identity fields, never from snippets."""
        return tuple(SourceItem.model_validate(item) for item in payload.get("source_items", ()))

    restore_source_items = rebuild_source_items

    @staticmethod
    def _validated_term(raw_term: Any) -> TermContribution:
        if isinstance(raw_term, TermContribution):
            return raw_term
        if isinstance(raw_term, Mapping):
            # The adapter accepts the forward-compatible extraction contract
            # (suggestion/reasoning/source refs) while validating the stable
            # term core against the current model boundary.
            raw_term = {
                key: value for key, value in raw_term.items()
                if key in TermContribution.model_fields
            }
        return TermContribution.model_validate(raw_term)

    @staticmethod
    def _term_data(term: TermContribution, raw_term: Any | None = None) -> dict[str, Any]:
        data = term.model_dump()
        for name in ("suggestion", "reasoning", "source_key", "source_key_refs", "source_aliases", "aliases"):
            if isinstance(raw_term, Mapping) and name in raw_term:
                data[name] = raw_term[name]
            elif raw_term is not None and hasattr(raw_term, name):
                data[name] = getattr(raw_term, name)
        return data

    def _collect_terms(
        self, extractions: Sequence[StructuredNeologismExtraction]
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        terms: dict[str, dict[str, Any]] = {}
        rejected: list[dict[str, Any]] = []
        for batch_index, extraction in enumerate(extractions):
            for raw_term in getattr(extraction, "terms", ()):
                try:
                    term = self._validated_term(raw_term)
                except ValidationError as exc:
                    rejected.append({
                        "batch_index": batch_index,
                        "reason": "term_validation_failed",
                        "diagnostic": str(exc),
                    })
                    continue
                data = self._term_data(term, raw_term)
                data["_batch_index"] = batch_index
                key = self._term_key(data["original"])
                current = terms.get(key)
                if current is None or data["confidence"] > current["confidence"]:
                    terms[key] = data
        return terms, rejected

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
        rejected: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        prepared = []
        for key, term in terms.items():
            if key in existing_keys:
                continue
            evidence = self._term_evidence(term["original"], parsed_files, term.get("evidence"))
            matches = duplicate_index.get(key, [])
            if evidence.get("rejected"):
                if rejected is not None:
                    rejected.append({
                        "batch_index": term.get("_batch_index"),
                        "term": term["original"],
                        **evidence["rejected"],
                    })
            elif evidence["context_snippets"]:
                prepared.append({**term, **evidence, "duplicate_matches": matches})
        return prepared

    @staticmethod
    def _term_evidence(
        original: str,
        parsed_files: Sequence[ParsedSourceFile],
        evidence: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source_lookup = {
            item.source_item_id: (source_file, item)
            for source_file in parsed_files
            for item in source_file.items
        }
        references = []
        if evidence:
            for entry in evidence:
                source_id = str(entry.get("source_item_id", ""))
                source = source_lookup.get(source_id)
                if source is None:
                    return {"rejected": {
                        "reason": "missing_source_item",
                        "source_item_id": source_id,
                    }}
                source_file, item = source
                references.append({
                    "source_item_id": source_id,
                    "relative_path": item.relative_path,
                    "item_key": item.item_key,
                    "source_order": item.source_order,
                })
        else:
            needle = original.casefold()
            references = [
                {
                    "source_item_id": item.source_item_id,
                    "relative_path": item.relative_path,
                    "item_key": item.item_key,
                    "source_order": item.source_order,
                }
                for source_file in parsed_files
                for item in source_file.items
                if needle in item.source_text.casefold()
            ]
        references = list({item["source_item_id"]: item for item in references}.values())
        snippets: list[str] = []
        source_files: list[str] = []
        context_evidence: list[ContextEvidence] = []
        frequency = 0
        for reference in references[:5]:
            source_file, item = source_lookup[reference["source_item_id"]]
            count = item.source_text.casefold().count(original.casefold())
            frequency += count or 1
            if item.source_text not in snippets:
                snippets.append(item.source_text)
            if reference["relative_path"] not in source_files:
                source_files.append(reference["relative_path"])
            context_evidence.append(
                ContextEvidence(snippet=item.source_text, source_file=reference["relative_path"], line=None)
            )
        return {
            "context_snippets": snippets,
            "source_files": source_files,
            "context_evidence": context_evidence,
            "frequency": frequency,
            "source_references": references[:5],
        }

    def _review_candidates(
        self,
        miner: Any,
        prepared: Sequence[dict[str, Any]],
        source_lang: str,
        target_lang: str,
        game_name: str,
        review_language: str,
        checkpoint_store: Any | None = None,
        run: Any | None = None,
    ) -> dict[str, Any]:
        review_items = [
            item
            for item in prepared
            if not self._target_suggestion(item["duplicate_matches"], target_lang)
            and (not item.get("suggestion") or not item.get("reasoning"))
        ]
        payloads = [
            {
                "original": item["original"],
                "category": item["category"],
                "frequency": item["frequency"],
                "contexts": item["context_snippets"],
            }
            for item in review_items
        ]
        reviews: dict[str, Any] = {}
        for offset in range(0, len(payloads), self.REVIEW_BATCH_SIZE):
            batch_index = offset // self.REVIEW_BATCH_SIZE
            source_ids = [
                source_id
                for item in review_items[offset : offset + self.REVIEW_BATCH_SIZE]
                for source_id in [ref["source_item_id"] for ref in item.get("source_references", [])]
            ]
            saved = checkpoint_store.get_batch(run.run_id, "review", batch_index) if checkpoint_store and run else None
            if saved and saved.status == "succeeded":
                reviews.update(self._restore_reviews(saved.payload.get("reviews", {})))
                continue
            try:
                result = miner.review_terms(
                    payloads[offset : offset + self.REVIEW_BATCH_SIZE],
                    source_lang=source_lang,
                    target_lang=target_lang,
                    game_name=game_name,
                    review_language=review_language,
                )
                reviews.update(result or {})
                if checkpoint_store and run:
                    checkpoint_store.save_batch(
                        run.run_id,
                        "review",
                        batch_index,
                        source_ids,
                        {"reviews": self._serialize_reviews(result or {})},
                    )
            except Exception as exc:
                if checkpoint_store and run:
                    checkpoint_store.save_batch(
                        run.run_id,
                        "review",
                        batch_index,
                        source_ids,
                        {"reviews": {}},
                        status="failed",
                        error={"type": type(exc).__name__, "message": str(exc)},
                    )
                raise
        return reviews

    @staticmethod
    def _serialize_reviews(reviews: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
        serialized = {}
        for original, review in reviews.items():
            if isinstance(review, Mapping):
                serialized[str(original)] = dict(review)
            else:
                serialized[str(original)] = {
                    "suggestion": getattr(review, "suggestion", ""),
                    "reasoning": getattr(review, "reasoning", ""),
                    "confidence": getattr(review, "confidence", 0.0),
                }
        return serialized

    @staticmethod
    def _restore_reviews(reviews: Mapping[str, Any]) -> dict[str, Any]:
        return {str(original): SimpleNamespace(**dict(review)) for original, review in reviews.items()}

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
            review_suggestion = review.get("suggestion", "") if isinstance(review, Mapping) else getattr(review, "suggestion", "")
            review_reasoning = review.get("reasoning", "") if isinstance(review, Mapping) else getattr(review, "reasoning", "")
            review_confidence = review.get("confidence", 0.0) if isinstance(review, Mapping) else getattr(review, "confidence", 0.0)
            candidates.append(
                Candidate(
                    id=str(uuid.uuid4()),
                    project_id=project_id,
                    original=item["original"],
                    context_snippets=item["context_snippets"],
                    suggestion=existing or item.get("suggestion") or review_suggestion,
                    reasoning=(
                        "An existing glossary entry matches this source term. Review whether to reuse it, "
                        "create a project override, or mark a new meaning."
                        if existing
                        else item.get("reasoning") or review_reasoning
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
                    confidence=max(item["confidence"], review_confidence or 0.0),
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
