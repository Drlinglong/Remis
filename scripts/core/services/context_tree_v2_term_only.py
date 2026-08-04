"""In-memory terms-only candidate results; the shared extraction prompt stays v10."""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from scripts.core.neologism_extraction import AnalysisScope, SourceEvidence
from scripts.schemas.context_candidate import normalized_match_key
try:
    from scripts.core.services.context_tree_v2_contract import TREE_V2_PROMPT_VERSION
except ImportError:  # The extraction slice may be integrated in a later commit.
    TREE_V2_PROMPT_VERSION = "context-archive-tree-v2"
from scripts.core.services.context_tree_v2_term_selection import (
    TermOnlyTerm,
    TermOnlyVariant,
    TermVariantSelectionState,
)

PROMPT_VERSION = TREE_V2_PROMPT_VERSION
PERSISTENCE_SCHEMA_VERSION = "context-tree-v2-term-only-v1"

PERSISTED_TERM_FIELDS = (
    "normalized_key",
    "original",
    "evidence",
    "variants",
    "selected_variant_id",
)
DISCARDED_FIELDS = (
    "catalog",
    "entities",
    "entity_digest",
    "event_context",
    "events",
    "facts",
    "local_fragments",
    "relationships",
    "unresolved_fragment_references",
    "unit_routes",
)
SKIPPED_STAGES = ("catalog", "entity_digest", "event_context")
_NARRATIVE_FIELDS = frozenset(
    "catalog delivery_assignments entities entity_digest event_context events facts "
    "global_event_orchestration groups local_fragments narrative narrative_context "
    "narrative_outputs relationships stories unresolved_fragment_references unit_routes".split()
)
_MISSING = object()
class TermOnlyContractError(ValueError):
    pass


class TermOnlySink(Protocol):
    def persist(self, payload: "TermOnlyPersistencePayload") -> Any:
        ...
class TermOnlyPersistencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PERSISTENCE_SCHEMA_VERSION
    analysis_scope: Literal["terms_only"] = "terms_only"
    prompt_version: str = PROMPT_VERSION
    persisted_term_fields: tuple[str, ...] = PERSISTED_TERM_FIELDS
    discarded_fields: tuple[str, ...] = DISCARDED_FIELDS
    terms: tuple[TermOnlyTerm, ...] = Field(default_factory=tuple, max_length=500)
    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
class TermOnlyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = PERSISTENCE_SCHEMA_VERSION
    analysis_scope: AnalysisScope = AnalysisScope.TERMS_ONLY
    prompt_version: str = PROMPT_VERSION
    source_language: str = "en"
    terms: list[TermOnlyTerm] = Field(default_factory=list, max_length=500)
    skipped_stages: dict[str, bool] = Field(
        default_factory=lambda: {stage: True for stage in SKIPPED_STAGES},
    )
    discarded_fields: tuple[str, ...] = DISCARDED_FIELDS
    @property
    def skipped(self) -> dict[str, bool]:
        return dict(self.skipped_stages)
    def term_for(self, term: str) -> TermOnlyTerm:
        key = normalized_match_key(term, self.source_language)
        match = next(
            (candidate for candidate in self.terms if candidate.normalized_key == key),
            None,
        )
        if match is None:
            raise KeyError(f"Unknown normalized term key: {key}")
        return match
    def approve_term(
        self,
        term: str,
        variant_id: str | None = None,
    ) -> TermOnlyVariant:
        return self.term_for(term).approve(variant_id)
    def approve_all(self) -> "TermOnlyResult":
        for term in self.terms:
            term.approve()
        return self
    def to_persistence_payload(self) -> TermOnlyPersistencePayload:
        terms = tuple(
            TermOnlyTerm.model_validate(term.model_dump(mode="python"))
            for term in self.terms
        )
        return TermOnlyPersistencePayload(
            schema_version=self.schema_version,
            analysis_scope="terms_only",
            prompt_version=self.prompt_version,
            terms=terms,
        )
    @property
    def persistence_payload(self) -> TermOnlyPersistencePayload:
        return self.to_persistence_payload()
    def persist(self, sink: Any) -> TermOnlyPersistencePayload:
        payload = self.to_persistence_payload()
        _send_to_sink(sink, payload)
        return payload
class ContextTreeV2TermOnlyService:
    PROMPT_VERSION = PROMPT_VERSION
    ANALYSIS_SCOPE = AnalysisScope.TERMS_ONLY
    SKIPPED_STAGES = SKIPPED_STAGES
    DISCARDED_FIELDS = DISCARDED_FIELDS
    def __init__(
        self,
        extractor: Any | None = None,
        sink: Any | None = None,
        *,
        source_language: str = "en",
        prompt_version: str = PROMPT_VERSION,
    ) -> None:
        if prompt_version != TREE_V2_PROMPT_VERSION:
            raise ValueError(
                "Terms-only extraction must retain the shared context-archive-tree-v2 prompt"
            )
        self.extractor = extractor
        self.sink = sink
        self.source_language = source_language
        self.prompt_version = prompt_version
    def build(
        self,
        extractions: Sequence[Any] | Any = (),
    ) -> TermOnlyResult:
        batches = _as_batch_sequence(extractions)
        aggregate_variants: dict[str, list[TermOnlyVariant]] = {}
        for batch_index, extraction in enumerate(batches):
            terms = _validate_terms_only_extraction(extraction)
            for term_index, raw_term in enumerate(_as_sequence(terms, "terms")):
                variant = self._variant(raw_term, batch_index, term_index)
                key = normalized_match_key(variant.original, self.source_language)
                aggregate_variants.setdefault(key, []).append(variant)
        terms = self._aggregates(aggregate_variants)
        return TermOnlyResult(
            analysis_scope=AnalysisScope.TERMS_ONLY,
            prompt_version=self.prompt_version,
            source_language=self.source_language,
            terms=terms,
        )
    def execute(
        self,
        batches: Sequence[Any] | Any = (),
        *,
        source_batches: Sequence[Any] | Any | None = None,
        extractor: Any | None = None,
        sink: Any = _MISSING,
        analysis_scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        scope: AnalysisScope | None = None,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
    ) -> TermOnlyResult:
        requested_scope = scope if scope is not None else analysis_scope
        if AnalysisScope(requested_scope) is not AnalysisScope.TERMS_ONLY:
            raise TermOnlyContractError("Context-tree term-only service requires TERMS_ONLY")
        selected_extractor = extractor if extractor is not None else self.extractor
        if selected_extractor is not None and (
            source_batches is not None or not _looks_like_extraction_sequence(batches)
        ):
            inputs = source_batches if source_batches is not None else batches
            extracted = self._invoke_extractor(
                selected_extractor,
                inputs,
                game_name=game_name,
                target_language=target_language,
                reasoning_language=reasoning_language,
            )
        else:
            extracted = batches
        result = self.build(extracted)
        selected_sink = self.sink if sink is _MISSING else sink
        if selected_sink is not None:
            result.persist(selected_sink)
        return result
    def run(self, *args: Any, **kwargs: Any) -> TermOnlyResult:
        return self.execute(*args, **kwargs)
    def _variant(self, raw_term: Any, batch_index: int, term_index: int) -> TermOnlyVariant:
        original = _required_text(raw_term, ("original", "term"), "original")
        key = normalized_match_key(original, self.source_language)
        if not key:
            raise TermOnlyContractError("A term original must have a non-empty normalized key")
        evidence = _coerce_evidence(_read(raw_term, "evidence", _MISSING))
        return TermOnlyVariant(
            variant_id=f"{key}::batch-{batch_index:04d}::term-{term_index:04d}",
            batch_index=batch_index,
            term_index=term_index,
            original=original,
            suggestion=_optional_text(raw_term, ("suggestion", "translation")),
            reasoning=_optional_text(raw_term, ("reasoning", "explanation")),
            evidence=evidence,
        )
    def _aggregates(
        self,
        variants_by_key: Mapping[str, list[TermOnlyVariant]],
    ) -> list[TermOnlyTerm]:
        aggregates = []
        for key in sorted(variants_by_key):
            variants = sorted(variants_by_key[key], key=lambda item: item.order_key)
            evidence = tuple(sorted(
                _deduplicate_evidence(item for variant in variants for item in variant.evidence),
                key=_evidence_sort_key,
            ))
            aggregates.append(TermOnlyTerm(
                normalized_key=key,
                original=variants[0].original,
                evidence=evidence,
                variants=variants,
            ))
        return aggregates
    @staticmethod
    def _invoke_extractor(
        extractor: Any,
        source_batches: Sequence[Any] | Any,
        *,
        game_name: str,
        target_language: str,
        reasoning_language: str,
    ) -> Sequence[Any]:
        kwargs = {
            "scope": AnalysisScope.TERMS_ONLY,
            "game_name": game_name,
            "target_language": target_language,
            "reasoning_language": reasoning_language,
            "prompt_version": TREE_V2_PROMPT_VERSION,
        }
        chunks = _as_source_batch_sequence(source_batches)
        for method_name in ("extract_chunks", "extract_batches"):
            method = getattr(extractor, method_name, None)
            if callable(method):
                return _as_batch_sequence(_call_supported(method, chunks, kwargs))
        method = next(
            (
                getattr(extractor, name, None)
                for name in ("extract_structured", "extract")
                if callable(getattr(extractor, name, None))
            ),
            None,
        )
        if callable(method):
            return _as_batch_sequence([
                _call_supported(method, chunk, kwargs)
                for chunk in chunks
            ])
        method = getattr(extractor, "run", None)
        if callable(method):
            return _as_batch_sequence(_call_supported(method, chunks, kwargs))
        if callable(extractor):
            return _as_batch_sequence(_call_supported(extractor, chunks, kwargs))
        raise TypeError("extractor must be a structured extractor, fake handler, or callable")
def _validate_terms_only_extraction(extraction: Any) -> Any:
    scope = _read(extraction, "analysis_scope", _MISSING)
    if scope is _MISSING:
        scope = _read(extraction, "scope", _MISSING)
    if isinstance(scope, Mapping):
        scope = scope.get("mode", scope.get("scope", _MISSING))
    if scope is not _MISSING and scope is not None:
        try:
            normalized_scope = AnalysisScope(scope)
        except ValueError as exc:
            raise TermOnlyContractError(f"Unknown extraction scope: {scope}") from exc
        if normalized_scope is not AnalysisScope.TERMS_ONLY:
            raise TermOnlyContractError("Narrative extraction is not accepted by terms-only mode")
    rejected = sorted(
        field for field in _NARRATIVE_FIELDS
        if _has_value(_read(extraction, field, _MISSING))
    )
    if rejected:
        raise TermOnlyContractError(
            "Terms-only extraction contains narrative fields: " + ", ".join(rejected)
        )
    terms = _read(extraction, "terms", _MISSING)
    if terms is _MISSING:
        raise TermOnlyContractError("Extraction record must expose a terms field")
    return terms
def _send_to_sink(sink: Any, payload: TermOnlyPersistencePayload) -> None:
    for method_name in ("persist", "save", "store", "write"):
        method = getattr(sink, method_name, None)
        if callable(method):
            method(payload)
            return
    if callable(sink):
        sink(payload)
        return
    raise TypeError("sink must expose persist(payload) or be callable")
def _call_supported(method: Callable[..., Any], argument: Any, kwargs: Mapping[str, Any]) -> Any:
    try:
        signature = inspect.signature(method)
    except (TypeError, ValueError):
        return method(argument, **dict(kwargs))
    accepts_kwargs = any(p.kind is inspect.Parameter.VAR_KEYWORD
                         for p in signature.parameters.values())
    supported = dict(kwargs) if accepts_kwargs else {
        name: value for name, value in kwargs.items() if name in signature.parameters}
    return method(argument, **supported)
def _read(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)
def _has_value(value: Any) -> bool:
    if value is _MISSING or value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    try:
        return len(value) > 0
    except TypeError:
        return True
def _as_sequence(value: Any, label: str) -> list[Any]:
    if value is _MISSING or value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        raise TermOnlyContractError(f"{label} must be a sequence")
    try:
        return list(value)
    except TypeError as exc:
        raise TermOnlyContractError(f"{label} must be a sequence") from exc
def _as_batch_sequence(value: Any) -> list[Any]:
    if _read(value, "terms", _MISSING) is not _MISSING:
        return [value]
    if isinstance(value, Mapping) and any(key in value for key in ("batches", "extractions")):
        return _as_sequence(value.get("batches", value.get("extractions", ())), "batches")
    if value is None:
        return []
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    return list(value)
def _looks_like_extraction_sequence(value: Any) -> bool:
    items = _as_batch_sequence(value)
    return bool(items) and all(_read(item, "terms", _MISSING) is not _MISSING for item in items)
def _as_source_batch_sequence(value: Any) -> list[list[Any]]:
    items = _as_sequence(value, "source_batches")
    if not items:
        return []
    if _read(items[0], "source_item_id", _MISSING) is not _MISSING:
        return [items]
    return [_as_sequence(item, "source batch") for item in items]
def _required_text(value: Any, names: Sequence[str], label: str) -> str:
    result = next(
        (candidate for name in names
         if (candidate := _read(value, name, _MISSING)) is not _MISSING
         and candidate is not None
         and str(candidate).strip()),
        _MISSING,
    )
    if result is _MISSING:
        raise TermOnlyContractError(f"Term record must contain {label}")
    return str(result).strip()
def _optional_text(value: Any, names: Sequence[str]) -> str | None:
    for name in names:
        candidate = _read(value, name, _MISSING)
        if candidate is not _MISSING and candidate is not None:
            text = str(candidate).strip()
            if text:
                return text
    return None
def _coerce_evidence(raw_evidence: Any) -> tuple[SourceEvidence, ...]:
    values = _as_sequence(raw_evidence, "evidence")
    if not values:
        raise TermOnlyContractError("Every term variant must retain source evidence")
    result = []
    for value in values:
        if isinstance(value, str):
            value = {"source_item_id": value}
        elif not isinstance(value, Mapping):
            value = {
                name: getattr(value, name)
                for name in (
                    "source_item_id", "snippet", "relative_path", "item_key",
                    "source_order", "provenance",
                )
                if hasattr(value, name)
            }
        try:
            result.append(SourceEvidence.model_validate(value))
        except Exception as exc:
            raise TermOnlyContractError("Invalid term source evidence") from exc
    return tuple(sorted(result, key=_evidence_sort_key))
def _deduplicate_evidence(values: Sequence[SourceEvidence]) -> list[SourceEvidence]:
    return list({_evidence_sort_key(value): value for value in values}.values())


def _evidence_sort_key(value: SourceEvidence) -> tuple[Any, ...]:
    return (value.source_item_id, value.relative_path, value.item_key or "",
            value.source_order if value.source_order is not None else -1,
            value.snippet or "", value.provenance)
# Compatibility aliases keep the slice easy to discover without creating a
# second service or a second prompt contract.
TermOnlyService = ContextTreeV2TermOnlyService
TermOnlyResultModel = TermOnlyResult
TermOnlyPersistenceContract = TermOnlyPersistencePayload


__all__ = [
    "ContextTreeV2TermOnlyService",
    "DISCARDED_FIELDS",
    "PERSISTED_TERM_FIELDS",
    "PROMPT_VERSION",
    "TREE_V2_PROMPT_VERSION",
    "SKIPPED_STAGES",
    "TermOnlyContractError",
    "TermOnlyPersistencePayload",
    "TermOnlyResult",
    "TermOnlyResultModel",
    "TermOnlyService",
    "TermOnlySink",
    "TermOnlyTerm",
    "TermOnlyVariant",
]
