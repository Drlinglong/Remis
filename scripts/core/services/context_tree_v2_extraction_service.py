"""Model boundary for lossless local-fragment and unit-route extraction."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Sequence

from pydantic import ValidationError

from scripts.core.context_local_units import ContextLocalUnitBuilder, LocalTextUnit
from scripts.core.neologism_extraction import (
    AnalysisScope,
    NeologismMiningError,
    SourceItem,
    StructuredNeologismExtractor,
)
from scripts.core.prompts.context_tree_v2_prompt import (
    extraction_prompt,
    fragment_repair_prompt,
    messages,
)
from scripts.core.services.context_tree_v2_contract import (
    ChunkEdgeMetadata,
    ContextTreeV2Extraction,
    FragmentRepairResponse,
    TREE_V2_PROMPT_VERSION,
)
from scripts.core.services.context_tree_v2_reconciliation_service import (
    ContextTreeV2ExtractionReconciliationService,
    MissingFragmentReferenceError,
)


class ContextTreeV2ExtractionService:
    """Run one v2 extraction call and repair only missing fragment definitions."""

    SCHEMA_VERSION = "context-tree-v2-extraction"
    PROMPT_VERSION = TREE_V2_PROMPT_VERSION
    SOURCE_ALIAS_PREFIX = "source_"
    SCHEMA_NAME = "remis_context_tree_v2_extraction"
    FRAGMENT_REPAIR_SCHEMA_NAME = "remis_context_tree_v2_fragment_repair"
    MAX_TOTAL_CONTRIBUTIONS = 250
    _BACKEND_METADATA_BY_DEFINITION = {
        "SourceEvidence": ("provenance",),
        "EntityContribution": ("provenance",),
        "FactContribution": ("provenance", "tentative"),
        "EventChainContribution": ("provenance", "tentative"),
        "RelationshipContribution": ("provenance", "tentative"),
    }
    _BACKEND_COLLECTION_METADATA = {
        "entities": {"provenance": "text_inferred"},
        "facts": {"provenance": "text_inferred", "tentative": True},
        "events": {"provenance": "text_inferred", "tentative": True},
        "relationships": {"provenance": "text_inferred", "tentative": True},
    }

    def __init__(self, handler: Any):
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    def extract_structured(
        self,
        source_items: Sequence[SourceItem],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
        core_units: Sequence[LocalTextUnit] | None = None,
        edge_units: Sequence[LocalTextUnit] = (),
        chunk_edge_metadata: ChunkEdgeMetadata | None = None,
    ) -> ContextTreeV2Extraction:
        """Compatibility-shaped entry point for extraction executors."""

        return self.extract(
            source_items,
            scope=scope,
            game_name=game_name,
            target_language=target_language,
            reasoning_language=reasoning_language,
            core_units=core_units,
            edge_units=edge_units,
            chunk_edge_metadata=chunk_edge_metadata,
        )

    def extract(
        self,
        source_items: Sequence[SourceItem],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
        core_units: Sequence[LocalTextUnit] | None = None,
        edge_units: Sequence[LocalTextUnit] = (),
        chunk_edge_metadata: ChunkEdgeMetadata | None = None,
    ) -> ContextTreeV2Extraction:
        scope = AnalysisScope(scope)
        items = self._validate_source_items(source_items)
        if not items:
            raise NeologismMiningError("Cannot extract from an empty source chunk")
        local_units = tuple(core_units) if core_units is not None else ContextLocalUnitBuilder.build(items)
        contextual_units = (*local_units, *edge_units)
        StructuredNeologismExtractor._validate_local_units(contextual_units, items)
        metadata = chunk_edge_metadata or self._default_edge_metadata(local_units, edge_units)
        self._validate_edge_metadata(metadata, local_units, edge_units)
        source_aliases = self._source_aliases(items)
        request_messages = self._request_messages(
            items,
            local_units,
            edge_units,
            metadata,
            scope=scope,
            game_name=game_name,
            target_language=target_language,
            reasoning_language=reasoning_language,
            source_aliases=source_aliases,
        )
        response = self._generate(
            request_messages,
            ContextTreeV2Extraction,
            self.SCHEMA_NAME,
            "Context tree v2 extraction",
        )
        extraction = self._parse_response(response, items, source_aliases, scope)
        if scope is AnalysisScope.TERMS_ONLY:
            return self._terms_only_result(extraction)
        expected_unit_ids = [unit.unit_id for unit in local_units]
        try:
            ContextTreeV2ExtractionReconciliationService.validate(
                extraction, expected_unit_ids,
            )
        except MissingFragmentReferenceError as error:
            return self._repair_missing_fragments(
                request_messages,
                response,
                extraction,
                error,
                expected_unit_ids,
            )
        extraction.diagnostics = {
            **extraction.diagnostics,
            "repair_count": 0,
            "complete": True,
            "chunk_edge_metadata": metadata.model_dump(),
            "prompt_version": TREE_V2_PROMPT_VERSION,
        }
        return extraction

    def _repair_missing_fragments(
        self,
        request_messages: list[dict[str, str]],
        original_response: str,
        extraction: ContextTreeV2Extraction,
        error: MissingFragmentReferenceError,
        expected_unit_ids: Sequence[str],
    ) -> ContextTreeV2Extraction:
        missing_ids = list(dict.fromkeys(fragment_id for _, fragment_id in error.references))
        repair_messages = [
            *request_messages,
            {"role": "assistant", "content": original_response},
            {
                "role": "user",
                "content": fragment_repair_prompt(missing_ids, expected_unit_ids),
            },
        ]
        try:
            repaired_response = self._generate(
                repair_messages,
                FragmentRepairResponse,
                self.FRAGMENT_REPAIR_SCHEMA_NAME,
                "Context tree v2 fragment repair",
            )
            repaired = self._parse_fragment_repair(repaired_response)
            reconciled = ContextTreeV2ExtractionReconciliationService.reconcile(
                extraction,
                expected_unit_ids,
                repaired.local_fragments,
                repair_attempts=1,
            )
            return reconciled.model_copy(update={
                "diagnostics": {
                    **extraction.diagnostics,
                    "repair_count": 1,
                    "repair_reason": "unknown_fragment_reference",
                    "repair_failed": bool(reconciled.unresolved_fragment_references),
                    "repair_requested_fragment_ids": missing_ids,
                    "repair_returned_fragment_ids": [
                        item.fragment_id for item in repaired.local_fragments
                    ],
                    "prompt_version": TREE_V2_PROMPT_VERSION,
                },
            })
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError, NeologismMiningError) as repair_error:
            self.logger.warning(
                "Tree v2 fragment repair failed; preserving unresolved links: %s",
                str(repair_error)[:500],
            )
            unresolved = ContextTreeV2ExtractionReconciliationService.reconcile(
                extraction,
                expected_unit_ids,
                (),
                repair_attempts=1,
            )
            unresolved.diagnostics = {
                **unresolved.diagnostics,
                "repair_count": 1,
                "repair_reason": "unknown_fragment_reference",
                "repair_failed": True,
                "repair_error": str(repair_error)[:500],
                "repair_requested_fragment_ids": missing_ids,
                "prompt_version": TREE_V2_PROMPT_VERSION,
            }
            return unresolved

    @staticmethod
    def _parse_fragment_repair(response: str) -> FragmentRepairResponse:
        payload = json.loads(ContextTreeV2ExtractionService._clean_json(response))
        if isinstance(payload, list):
            payload = {"local_fragments": payload}
        return FragmentRepairResponse.model_validate(payload)

    @classmethod
    def _parse_response(
        cls,
        response: str,
        source_items: Sequence[SourceItem],
        source_aliases: Dict[str, str],
        scope: AnalysisScope,
    ) -> ContextTreeV2Extraction:
        payload = json.loads(cls._clean_json(response))
        if not isinstance(payload, dict):
            raise ValueError("Context tree v2 extraction must be a JSON object")
        cls._normalize_backend_metadata(payload, source_aliases)
        extraction = ContextTreeV2Extraction.model_validate(payload)
        if sum(len(values) for values in extraction.contribution_lists()) > cls.MAX_TOTAL_CONTRIBUTIONS:
            raise NeologismMiningError(
                "Context tree v2 extraction exceeded the contribution safety limit"
            )
        lookup = {item.source_item_id: item for item in source_items}
        extraction.terms = StructuredNeologismExtractor._filter_grounded_contributions(
            extraction.terms, lookup,
        )
        extraction.entities = StructuredNeologismExtractor._filter_grounded_contributions(
            extraction.entities, lookup,
        )
        extraction.facts = StructuredNeologismExtractor._filter_grounded_contributions(
            extraction.facts, lookup,
        )
        extraction.events = StructuredNeologismExtractor._filter_grounded_contributions(
            extraction.events, lookup,
        )
        extraction.relationships = StructuredNeologismExtractor._filter_grounded_contributions(
            extraction.relationships, lookup,
        )
        if scope is AnalysisScope.TERMS_ONLY:
            return cls._terms_only_result(extraction)
        return extraction

    @classmethod
    def _model_response_schema(cls) -> dict[str, Any]:
        schema = ContextTreeV2Extraction.model_json_schema()
        definitions = schema.get("$defs", {})
        for definition_name, fields in cls._BACKEND_METADATA_BY_DEFINITION.items():
            definition = definitions.get(definition_name, {})
            properties = definition.get("properties", {})
            required = definition.get("required", [])
            for field_name in fields:
                properties.pop(field_name, None)
            definition["required"] = [field for field in required if field not in fields]
        properties = schema.get("properties", {})
        for field_name in ("diagnostics", "unresolved_fragment_references"):
            properties.pop(field_name, None)
        required = schema.get("required", [])
        schema["required"] = [
            field for field in required
            if field not in {"diagnostics", "unresolved_fragment_references"}
        ]
        return schema

    @classmethod
    def _normalize_backend_metadata(
        cls,
        payload: dict[str, Any],
        source_aliases: Dict[str, str],
    ) -> None:
        for collection_name in (
            "local_fragments", "unit_routes", "entities", "terms",
            "facts", "events", "relationships",
        ):
            if payload.get(collection_name) is None:
                payload[collection_name] = []
        payload.pop("diagnostics", None)
        payload.pop("unresolved_fragment_references", None)
        aliases = {alias: source_id for source_id, alias in source_aliases.items()}
        for collection_name, fixed_fields in cls._BACKEND_COLLECTION_METADATA.items():
            for contribution in payload.get(collection_name) or []:
                if not isinstance(contribution, dict):
                    continue
                contribution.update(fixed_fields)
                for evidence in contribution.get("evidence") or []:
                    if not isinstance(evidence, dict):
                        continue
                    source_alias = evidence.get("source_item_id")
                    if source_alias in aliases:
                        evidence["source_item_id"] = aliases[source_alias]
                    evidence["provenance"] = "text_inferred"
        for contribution in payload.get("terms") or []:
            if not isinstance(contribution, dict):
                continue
            for evidence in contribution.get("evidence") or []:
                if isinstance(evidence, dict) and evidence.get("source_item_id") in aliases:
                    evidence["source_item_id"] = aliases[evidence["source_item_id"]]

    @classmethod
    def _request_messages(
        cls,
        items: Sequence[SourceItem],
        core_units: Sequence[LocalTextUnit],
        edge_units: Sequence[LocalTextUnit],
        metadata: ChunkEdgeMetadata,
        *,
        scope: AnalysisScope,
        game_name: str,
        target_language: str,
        reasoning_language: str,
        source_aliases: Dict[str, str],
    ) -> list[dict[str, str]]:
        payload = {
            "scope": scope.value,
            "source_items": [
                {**item.model_dump(), "source_item_id": source_aliases[item.source_item_id]}
                for item in items
            ],
            "local_text_units": [
                *(
                    unit.prompt_payload(source_aliases, context_role="core")
                    for unit in core_units
                ),
                *(
                    unit.prompt_payload(source_aliases, context_role="edge")
                    for unit in edge_units
                ),
            ] if scope is AnalysisScope.NARRATIVE_CONTEXT else [],
            "core_unit_ids": [unit.unit_id for unit in core_units],
            "chunk_edge_metadata": metadata.model_dump(),
        }
        return messages(
            extraction_prompt(
                scope=scope.value,
                game_name=game_name,
                target_language=target_language,
                reasoning_language=reasoning_language,
            ),
            payload,
        )

    def _generate(
        self,
        request_messages: list[dict[str, str]],
        response_model: type[Any],
        schema_name: str,
        stage_label: str,
    ) -> str:
        try:
            structured = getattr(self.handler, "generate_structured_with_messages", None)
            if structured is not None:
                response = structured(
                    request_messages,
                    schema=(
                        self._model_response_schema()
                        if response_model is ContextTreeV2Extraction
                        else response_model.model_json_schema()
                    ),
                    schema_name=schema_name,
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(request_messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"{stage_label} request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError(f"{stage_label} returned an empty response")
        return response.strip()

    @staticmethod
    def _terms_only_result(extraction: ContextTreeV2Extraction) -> ContextTreeV2Extraction:
        discarded = {
            field: len(getattr(extraction, field))
            for field in (
                "local_fragments", "unit_routes", "entities", "facts",
                "events", "relationships",
            )
            if getattr(extraction, field)
        }
        return extraction.model_copy(update={
            "local_fragments": [],
            "unit_routes": [],
            "entities": [],
            "facts": [],
            "events": [],
            "relationships": [],
            "diagnostics": {
                **extraction.diagnostics,
                "repair_count": 0,
                "complete": True,
                "terms_only_discarded_fields": discarded,
                "prompt_version": TREE_V2_PROMPT_VERSION,
            },
        })

    @classmethod
    def _source_aliases(cls, source_items: Sequence[SourceItem]) -> Dict[str, str]:
        return {
            item.source_item_id: f"{cls.SOURCE_ALIAS_PREFIX}{index}"
            for index, item in enumerate(source_items)
        }

    @staticmethod
    def _validate_source_items(source_items: Sequence[SourceItem]) -> list[SourceItem]:
        items = list(source_items)
        ids = [item.source_item_id for item in items]
        if len(ids) != len(set(ids)):
            raise NeologismMiningError("Source item identities must be unique within one chunk")
        return items

    @staticmethod
    def _default_edge_metadata(
        core_units: Sequence[LocalTextUnit],
        edge_units: Sequence[LocalTextUnit],
    ) -> ChunkEdgeMetadata:
        return ChunkEdgeMetadata(
            chunk_index=0,
            chunk_count=1,
            core_unit_ids=[unit.unit_id for unit in core_units],
            edge_after_unit_ids=[unit.unit_id for unit in edge_units],
        )

    @staticmethod
    def _validate_edge_metadata(
        metadata: ChunkEdgeMetadata,
        core_units: Sequence[LocalTextUnit],
        edge_units: Sequence[LocalTextUnit],
    ) -> None:
        core_ids = {unit.unit_id for unit in core_units}
        edge_ids = {unit.unit_id for unit in edge_units}
        if set(metadata.core_unit_ids) != core_ids:
            raise ValueError("chunk edge metadata core_unit_ids do not match the call")
        if set(metadata.edge_before_unit_ids) | set(metadata.edge_after_unit_ids) != edge_ids:
            raise ValueError("chunk edge metadata edge unit IDs do not match the call")

    @staticmethod
    def _clean_json(response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()
