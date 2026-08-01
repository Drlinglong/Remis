"""Bounded backend orchestration for neologism and Mod Context analysis."""

from __future__ import annotations

import hashlib
import threading
import uuid
from collections import defaultdict
from typing import Any, Callable, Iterable, Sequence

from scripts.core.api_handler import get_handler
from scripts.core.context_service import ContextService
from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceItem,
    StructuredNeologismExtraction,
)
from scripts.core.neologism_manager import Candidate, ContextEvidence, neologism_manager
from scripts.core.neologism_miner import NeologismMiner
from scripts.core.services.context_source_parser import ContextSourceParser, ParsedSourceFile
from scripts.core.services.context_synthesis_service import ContextSynthesisService
from scripts.core.services.source_snapshot_service import (
    SourceItemIdentity,
    SourceItemSnapshot,
    SourceSnapshot,
    SourceSnapshotService,
    SourceChangeKind,
)
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextRelease,
    ContextReleaseMetadata,
    ContextSourceItem,
)
from scripts.shared import task_state


class ContextWorkflowService:
    """Own the maintained scan workflow while keeping domain ports injectable."""

    CHUNK_SIZE = 50
    REVIEW_BATCH_SIZE = 20
    SCHEMA_VERSION = "context-v1"
    PROMPT_VERSION = "context-synthesis-v1"
    ACTIVE_STATUSES = {"queued", "starting", "running"}

    def __init__(
        self,
        repository: Any,
        *,
        handler_factory: Callable[..., Any] = get_handler,
        candidate_store: Any = neologism_manager,
        task_backend: Any = task_state,
        source_parser: ContextSourceParser | None = None,
        snapshot_service: SourceSnapshotService | None = None,
        miner_factory: Callable[[Any], Any] = NeologismMiner,
        synthesizer_factory: Callable[[Any], Any] = ContextSynthesisService,
        context_service: ContextService | None = None,
    ):
        self.repository = repository
        self.context_service = context_service or ContextService(repository)
        self.handler_factory = handler_factory
        self.candidate_store = candidate_store
        self.task_backend = task_backend
        self.source_parser = source_parser or ContextSourceParser()
        self.snapshot_service = snapshot_service or SourceSnapshotService()
        self.miner_factory = miner_factory
        self.synthesizer_factory = synthesizer_factory
        self._status_lock = threading.RLock()
        self._statuses: dict[str, dict[str, Any]] = {}

    def reserve(self, project_id: str, task_id: str, scope: AnalysisScope) -> bool:
        """Atomically reserve one context-analysis run for a project."""
        normalized = AnalysisScope(scope)
        with self._status_lock:
            current = self._statuses.get(project_id)
            if current and current.get("status") in self.ACTIVE_STATUSES:
                return False
            self._statuses[project_id] = {
                **self._idle_status(),
                "status": "queued",
                "task_id": task_id,
                "analysis_scope": normalized.value,
            }
        return True

    @staticmethod
    def _idle_status() -> dict[str, Any]:
        return {
            "status": "idle",
            "processed_files": 0,
            "total_files": 0,
            "new_terms": 0,
            "duplicate_terms": 0,
            "current_file": None,
            "error": None,
            "task_id": None,
            "analysis_scope": AnalysisScope.TERMS_ONLY.value,
            "source_snapshot_hash": None,
            "context_release_id": None,
        }

    def release_reservation(self, project_id: str, task_id: str) -> None:
        """Release a queued reservation when task creation fails."""
        with self._status_lock:
            current = self._statuses.get(project_id)
            if (
                current
                and current.get("task_id") == task_id
                and current.get("status") == "queued"
            ):
                self._statuses[project_id] = self._idle_status()

    def get_status(self, project_id: str) -> dict[str, Any]:
        with self._status_lock:
            status = self._statuses.get(project_id)
            if status is not None:
                return dict(status)
        return self._idle_status()

    def run(
        self,
        project_id: str,
        file_paths: Sequence[str],
        source_root: str,
        api_provider: str,
        *,
        source_lang: str = "en",
        target_lang: str = "zh-CN",
        game_name: str = "Paradox Game",
        task_id: str | None = None,
        duplicate_index: dict[str, list[dict[str, Any]]] | None = None,
        model_name: str | None = None,
        review_language: str = "en",
        analysis_scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        upstream_version: str | None = None,
        analysis_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = AnalysisScope(analysis_scope)
        parsed_files: tuple[ParsedSourceFile, ...] = ()
        processed_files = 0
        try:
            parsed_files = self.source_parser.parse_files(file_paths, source_root)
            snapshot = self.source_parser.build_snapshot(parsed_files, self.snapshot_service)
            parent = self._latest_release(project_id) if scope is AnalysisScope.NARRATIVE_CONTEXT else None
            diff = self._source_diff(parent, snapshot)
            self._running(project_id, task_id, scope, parsed_files, snapshot, diff)
            handler = self.handler_factory(api_provider, model_name=model_name)
            miner = self.miner_factory(handler)
            extractions = self._extract(miner, parsed_files, scope, game_name, task_id)
            terms_result = self._finish_terms_only(
                project_id, parsed_files, extractions, miner, duplicate_index or {},
                source_lang, target_lang, game_name, review_language,
            )
            if scope is AnalysisScope.TERMS_ONLY:
                result = terms_result
            else:
                result = self._finish_context(
                    project_id, parsed_files, snapshot, diff, parent, extractions,
                    handler, api_provider, model_name, upstream_version, analysis_config,
                )
                result.update({"new_terms": terms_result["new_terms"], "duplicate_terms": terms_result["duplicate_terms"]})
            self._complete(project_id, task_id, result, len(parsed_files))
            return result
        except Exception as exc:
            self._failed(project_id, task_id, len(parsed_files), processed_files, exc)
            raise

    def _extract(
        self,
        miner: Any,
        parsed_files: Sequence[ParsedSourceFile],
        scope: AnalysisScope,
        game_name: str,
        task_id: str | None,
    ) -> list[StructuredNeologismExtraction]:
        chunks = list(self._chunks(item for source_file in parsed_files for item in source_file.items))
        results: list[StructuredNeologismExtraction] = []
        for index, chunk in enumerate(chunks, start=1):
            results.append(miner.extract_structured(list(chunk), scope=scope, game_name=game_name))
            self._task_update(
                task_id,
                progress={"current_batch": index, "total_batches": len(chunks), "stage": "Extracting"},
                fields={"stage_code": "extracting"},
                push=False,
            )
        return results

    def _finish_terms_only(
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

    def _finish_context(
        self,
        project_id: str,
        parsed_files: Sequence[ParsedSourceFile],
        snapshot: SourceSnapshot,
        diff: Any,
        parent: ContextRelease | None,
        extractions: Sequence[StructuredNeologismExtraction],
        handler: Any,
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        sources = self._persist_sources(project_id, parsed_files, snapshot.source_snapshot_hash)
        contributions = self._persist_contributions(extractions, sources)
        if not contributions:
            return {
                "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
                "new_terms": 0,
                "context_release_id": None,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "affected_source_items": self._affected_items(diff),
            }
        aggregates = self._build_aggregates(project_id, contributions)
        for aggregate in aggregates:
            self.repository.save_aggregate(aggregate)
        syntheses = self.synthesizer_factory(handler).synthesize(aggregates, contributions, sources)
        metadata = self._metadata(
            snapshot, parsed_files, diff, parent, api_provider, model_name,
            upstream_version, analysis_config,
        )
        draft = self.context_service.start_draft(project_id, parent.release_id if parent else None)
        release = self.context_service.publish_draft(
            draft.draft_id, metadata, [item.aggregate_id for item in aggregates], syntheses
        )
        return {
            "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT.value,
            "new_terms": 0,
            "context_release_id": release.release_id,
            "source_snapshot_hash": snapshot.source_snapshot_hash,
            "affected_source_items": self._affected_items(diff),
            "parent_release_id": parent.release_id if parent else None,
        }

    def _persist_sources(
        self, project_id: str, parsed_files: Sequence[ParsedSourceFile], snapshot_hash: str
    ) -> dict[str, ContextSourceItem]:
        sources: dict[str, ContextSourceItem] = {}
        for source_file in parsed_files:
            for item in source_file.items:
                source = ContextSourceItem(
                    source_item_id=item.source_item_id,
                    project_id=project_id,
                    source_type="localization",
                    source_ref=f"{item.relative_path}::{item.source_order}:{item.item_key or ''}",
                    content=item.source_text,
                    content_hash=hashlib.sha256(item.source_text.encode("utf-8")).hexdigest(),
                    metadata={
                        "relative_path": item.relative_path,
                        "item_key": item.item_key,
                        "source_order": item.source_order,
                        "source_snapshot_hash": snapshot_hash,
                    },
                )
                existing = self.repository.get_source_item(source.source_item_id)
                sources[source.source_item_id] = existing or self.repository.create_source_item(source)
        return sources

    def _persist_contributions(
        self,
        extractions: Sequence[StructuredNeologismExtraction],
        sources: dict[str, ContextSourceItem],
    ) -> dict[str, ContextContribution]:
        contributions: dict[str, ContextContribution] = {}
        for extraction in extractions:
            for item in self._all_contributions(extraction):
                evidence = [entry.model_dump() for entry in item.evidence]
                source_item_id = evidence[0]["source_item_id"]
                if source_item_id not in sources:
                    raise ValueError("Extraction evidence referenced a source outside the parsed snapshot")
                contribution = ContextContribution(
                    contribution_id=str(uuid.uuid4()),
                    source_item_id=source_item_id,
                    contribution_type=self._contribution_type(item),
                    subject_key=self._subject_key(item),
                    payload={**item.model_dump(), "evidence": evidence},
                    provenance="text_inferred",
                )
                self.repository.create_contribution(contribution)
                contributions[contribution.contribution_id] = contribution
        return contributions

    @staticmethod
    def _all_contributions(extraction: StructuredNeologismExtraction) -> list[Any]:
        return [
            *extraction.terms, *extraction.entities, *extraction.facts,
            *extraction.events, *extraction.relationships,
        ]

    @staticmethod
    def _contribution_type(item: Any) -> str:
        name = item.__class__.__name__
        return {"TermContribution": "mention", "EntityContribution": "mention", "FactContribution": "fact",
                "EventChainContribution": "event", "RelationshipContribution": "relationship"}[name]

    @staticmethod
    def _subject_key(item: Any) -> str:
        if item.__class__.__name__ == "EventChainContribution":
            return f"event:{item.chain_id.strip().casefold()}"
        value = getattr(item, "original", None) or getattr(item, "name", None) or getattr(item, "subject", None)
        return f"entity:{str(value).strip().casefold()}"

    def _build_aggregates(
        self, project_id: str, contributions: dict[str, ContextContribution]
    ) -> list[ContextAggregate]:
        groups: dict[str, list[str]] = defaultdict(list)
        for contribution in contributions.values():
            groups[contribution.subject_key].append(contribution.contribution_id)
        groups["project:summary"] = list(contributions)
        aggregates = []
        for aggregate_key, contribution_ids in sorted(groups.items()):
            aggregate_type = "project" if aggregate_key == "project:summary" else (
                "event" if aggregate_key.startswith("event:") else "entity"
            )
            aggregate_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"remis:{project_id}:{aggregate_key}"))
            aggregates.append(ContextAggregate(
                aggregate_id=aggregate_id,
                project_id=project_id,
                aggregate_type=aggregate_type,
                aggregate_key=aggregate_key,
                payload={"active_contribution_count": len(contribution_ids)},
                contribution_ids=contribution_ids,
            ))
        return aggregates

    def _metadata(
        self,
        snapshot: SourceSnapshot,
        parsed_files: Sequence[ParsedSourceFile],
        diff: Any,
        parent: ContextRelease | None,
        api_provider: str,
        model_name: str | None,
        upstream_version: str | None,
        analysis_config: dict[str, Any] | None,
    ) -> ContextReleaseMetadata:
        config = dict(analysis_config or {})
        config.update({
            "reuse_strategy": "full_reextract",
            "source_items": [
                {
                    "relative_path": item.identity.relative_path,
                    "item_key": item.identity.item_key,
                    "source_order": item.identity.source_order,
                    "source_sha256": item.source_sha256,
                }
                for item in snapshot.items
            ],
            "affected_source_items": self._affected_items(diff),
        })
        return ContextReleaseMetadata(
            source_snapshot_hash=snapshot.source_snapshot_hash,
            analysis_scope={
                "mode": AnalysisScope.NARRATIVE_CONTEXT.value,
                "files": [item.relative_path for item in parsed_files],
            },
            schema_version=self.SCHEMA_VERSION,
            prompt_version=self.PROMPT_VERSION,
            provider_id=api_provider,
            model_id=model_name or f"{api_provider}-default",
            analysis_config=config,
            parent_release_id=parent.release_id if parent else None,
            upstream_version=upstream_version,
        )

    @staticmethod
    def _source_diff(parent: ContextRelease | None, current: SourceSnapshot) -> Any:
        if not parent:
            return current.diff(None)
        previous_items = tuple(
            SourceItemSnapshot(
                identity=SourceItemIdentity(
                    item["relative_path"], item.get("item_key"), item.get("source_order")
                ),
                source_sha256=item["source_sha256"],
            )
            for item in parent.metadata.analysis_config.get("source_items", [])
        )
        previous = SourceSnapshot(files=(), source_snapshot_hash=parent.metadata.source_snapshot_hash, items=previous_items)
        return current.diff(previous)

    @staticmethod
    def _affected_items(diff: Any) -> list[dict[str, str]]:
        return [
            {"relative_path": item.identity.relative_path, "item_key": item.identity.item_key or "", "kind": item.kind.value}
            for item in diff.item_changes
            if item.kind is not SourceChangeKind.UNCHANGED
        ]

    def _latest_release(self, project_id: str) -> ContextRelease | None:
        releases = self.repository.list_releases(project_id)
        return releases[0] if releases else None

    @staticmethod
    def _chunks(items: Iterable[SourceItem]) -> Iterable[tuple[SourceItem, ...]]:
        current: list[SourceItem] = []
        for item in items:
            current.append(item)
            if len(current) >= ContextWorkflowService.CHUNK_SIZE:
                yield tuple(current)
                current = []
        if current:
            yield tuple(current)

    @staticmethod
    def _merge_terms(extractions: Sequence[StructuredNeologismExtraction]) -> dict[str, dict[str, Any]]:
        terms: dict[str, dict[str, Any]] = {}
        for extraction in extractions:
            for term in extraction.terms:
                key = ContextWorkflowService._term_key(term.original)
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
    def _term_evidence(original: str, parsed_files: Sequence[ParsedSourceFile]) -> dict[str, Any]:
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
                    context_evidence.append(ContextEvidence(
                        snippet=item.source_text, source_file=str(source_file.path), line=None
                    ))
            if matched:
                source_files.append(str(source_file.path))
        return {
            "context_snippets": snippets,
            "source_files": source_files,
            "context_evidence": context_evidence,
            "frequency": frequency,
        }

    def _review_candidates(
        self, miner: Any, prepared: Sequence[dict[str, Any]], source_lang: str,
        target_lang: str, game_name: str, review_language: str,
    ) -> dict[str, Any]:
        payloads = [
            {
                "original": item["original"], "category": item["category"],
                "frequency": item["frequency"], "contexts": item["context_snippets"],
            }
            for item in prepared
            if not self._target_suggestion(item["duplicate_matches"], target_lang)
        ]
        reviews: dict[str, Any] = {}
        for offset in range(0, len(payloads), self.REVIEW_BATCH_SIZE):
            reviews.update(miner.review_terms(
                payloads[offset:offset + self.REVIEW_BATCH_SIZE], source_lang=source_lang,
                target_lang=target_lang, game_name=game_name, review_language=review_language,
            ))
        return reviews

    def _build_candidates(
        self, project_id: str, prepared: Sequence[dict[str, Any]], reviews: dict[str, Any],
        source_lang: str, target_lang: str, review_language: str,
    ) -> list[Candidate]:
        candidates = []
        for item in prepared:
            existing = self._target_suggestion(item["duplicate_matches"], target_lang)
            review = reviews.get(item["original"])
            candidates.append(Candidate(
                id=str(uuid.uuid4()), project_id=project_id, original=item["original"],
                context_snippets=item["context_snippets"], suggestion=existing or (review.suggestion if review else ""),
                reasoning=(
                    "An existing glossary entry matches this source term. Review whether to reuse it, "
                    "create a project override, or mark a new meaning."
                    if existing else review.reasoning
                ), source_file=item["source_files"][0] if item["source_files"] else None,
                source_files=item["source_files"], context_evidence=item["context_evidence"],
                source_lang=source_lang, target_lang=target_lang, review_language=review_language,
                duplicate_matches=item["duplicate_matches"], frequency=item["frequency"],
                category=item["category"], confidence=max(item["confidence"], review.confidence if review else 0.0),
            ))
        return candidates

    @staticmethod
    def _target_suggestion(matches: list[dict[str, Any]], target_lang: str) -> str:
        for match in matches:
            translations = match.get("translations") or {}
            suggestion = translations.get(target_lang) or translations.get(target_lang.replace("-", "_"))
            if suggestion:
                return str(suggestion)
        return ""

    def _running(
        self, project_id: str, task_id: str | None, scope: AnalysisScope,
        parsed_files: Sequence[ParsedSourceFile], snapshot: SourceSnapshot, diff: Any,
    ) -> None:
        self._set_status(
            project_id, status="running", task_id=task_id, processed_files=0,
            total_files=len(parsed_files), analysis_scope=scope.value,
            source_snapshot_hash=snapshot.source_snapshot_hash,
            affected_source_items=self._affected_items(diff),
        )
        self._task_update(
            task_id, status="running", message="Context analysis started.",
            fields={"stage_code": "extracting", "workflow_context": {"analysis_scope": scope.value}},
        )

    def _complete(self, project_id: str, task_id: str | None, result: dict[str, Any], total_files: int) -> None:
        self._set_status(
            project_id, status="completed", processed_files=total_files, total_files=total_files,
            current_file=None, error=None, **result,
        )
        self._task_update(
            task_id, status="completed", message="Context analysis completed.",
            progress={"current": total_files, "total": total_files, "percent": 100, "stage": "Completed"},
            summary=result, fields={"stage_code": "completed"},
        )

    def _failed(self, project_id: str, task_id: str | None, total_files: int, processed_files: int, error: Exception) -> None:
        message = str(error) or error.__class__.__name__
        self._set_status(project_id, status="failed", total_files=total_files, processed_files=processed_files, error=message)
        self._task_update(
            task_id, status="failed", message=message, fields={
                "stage_code": "failed", "attention_reason": message,
                "attention_reason_code": "context_analysis_failed",
            },
        )

    def _set_status(self, project_id: str, **updates: Any) -> None:
        with self._status_lock:
            current = self._statuses.setdefault(project_id, self.get_status(project_id))
            current.update(updates)

    def _task_update(self, task_id: str | None, **updates: Any) -> None:
        if task_id:
            push = updates.pop("push", True)
            self.task_backend.update_task(task_id, push=push, **updates)
