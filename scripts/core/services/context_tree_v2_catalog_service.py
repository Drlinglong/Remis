"""ID-only global catalog service for context archive tree v2."""

from __future__ import annotations

import json
from typing import Any, Sequence

from pydantic import ValidationError

from scripts.core.neologism_extraction import NeologismMiningError
from scripts.core.prompts.context_tree_v2_prompt import catalog_prompt, messages
from scripts.core.services.context_tree_v2_contract import (
    ChunkEdgeMetadata,
    ContextTreeCatalog,
    LocalFragment,
    TREE_V2_PROMPT_VERSION,
    TreeCatalogResult,
)


class ContextTreeV2CatalogService:
    """Ask the model for relationships between immutable fragment IDs only."""

    SCHEMA_VERSION = "context-tree-v2-catalog"
    PROMPT_VERSION = TREE_V2_PROMPT_VERSION
    SCHEMA_NAME = "remis_context_tree_v2_catalog"
    REPAIR_ERROR_CHARS = 1_500

    def __init__(self, handler: Any):
        self.handler = handler

    def build_catalog(
        self,
        fragment_cards: Sequence[LocalFragment],
        *,
        chunk_edge_metadata: Sequence[ChunkEdgeMetadata] = (),
        description_language: str = "en",
    ) -> TreeCatalogResult:
        cards = self._normalize_cards(fragment_cards)
        if not cards:
            return TreeCatalogResult(
                catalog=ContextTreeCatalog(),
                diagnostics={
                    "model_call_count": 0,
                    "fragment_count": 0,
                    "prompt_version": TREE_V2_PROMPT_VERSION,
                },
            )
        metadata = [
            item if isinstance(item, ChunkEdgeMetadata)
            else ChunkEdgeMetadata.model_validate(item)
            for item in chunk_edge_metadata
        ]
        payload = {
            "description_language": description_language,
            "fragment_cards": [card.model_dump() for card in cards],
            "chunk_edge_metadata": [item.model_dump() for item in metadata],
        }
        request_messages = messages(catalog_prompt(description_language), payload)
        response = self._generate(request_messages, "Context tree v2 catalog")
        try:
            catalog = self._parse_and_validate(response, cards)
            return self._result(catalog, repair_count=0, cards=cards)
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            repair_messages = [
                *request_messages,
                {"role": "assistant", "content": response},
                {
                    "role": "user",
                    "content": self._repair_instruction(first_error, cards),
                },
            ]
            repaired = self._generate(repair_messages, "Context tree v2 catalog repair")
            try:
                catalog = self._parse_and_validate(repaired, cards)
            except (json.JSONDecodeError, ValidationError, ValueError) as second_error:
                raise NeologismMiningError(
                    "Context tree v2 catalog failed after one repair "
                    f"({self._error_category(second_error)}): "
                    f"{str(second_error)[: self.REPAIR_ERROR_CHARS]}"
                ) from second_error
            result = self._result(
                catalog,
                repair_count=1,
                cards=cards,
                repair_reason=self._error_category(first_error),
                repair_detail=str(first_error)[: self.REPAIR_ERROR_CHARS],
            )
            return result

    @classmethod
    def validate_catalog(
        cls,
        catalog: ContextTreeCatalog,
        fragment_cards: Sequence[LocalFragment],
    ) -> None:
        known = {card.fragment_id for card in fragment_cards}
        grouped = [fragment_id for group in catalog.groups for fragment_id in group.fragment_ids]
        grouped_set = set(grouped)
        unresolved = list(catalog.unresolved_fragment_ids)
        unresolved_set = set(unresolved)
        duplicate_grouped = cls._duplicates(grouped)
        unknown = (grouped_set | unresolved_set) - known
        missing = known - (grouped_set | unresolved_set)
        overlap = grouped_set & unresolved_set
        if duplicate_grouped or unknown or missing or overlap:
            raise ValueError(
                "Tree v2 catalog fragment coverage invalid: "
                f"duplicate={duplicate_grouped}, unknown={sorted(unknown)}, "
                f"missing={sorted(missing)}, overlap={sorted(overlap)}"
            )

    @staticmethod
    def _normalize_cards(fragment_cards: Sequence[LocalFragment]) -> list[LocalFragment]:
        cards = [
            card if isinstance(card, LocalFragment) else LocalFragment.model_validate(card)
            for card in fragment_cards
        ]
        ids = [card.fragment_id for card in cards]
        duplicates = ContextTreeV2CatalogService._duplicates(ids)
        if duplicates:
            raise ValueError(f"Local fragment card identities are duplicated: {duplicates}")
        return cards

    @classmethod
    def _parse_and_validate(
        cls,
        response: str,
        cards: Sequence[LocalFragment],
    ) -> ContextTreeCatalog:
        payload = json.loads(cls._clean_json(response))
        catalog = ContextTreeCatalog.model_validate(payload)
        cls.validate_catalog(catalog, cards)
        return catalog

    @staticmethod
    def _result(
        catalog: ContextTreeCatalog,
        *,
        repair_count: int,
        cards: Sequence[LocalFragment],
        repair_reason: str | None = None,
        repair_detail: str | None = None,
    ) -> TreeCatalogResult:
        return TreeCatalogResult(
            catalog=catalog,
            repair_count=repair_count,
            repair_reason=repair_reason,
            repair_detail=repair_detail,
            diagnostics={
                "model_call_count": 1 + repair_count,
                "fragment_count": len(cards),
                "group_count": len(catalog.groups),
                "unresolved_fragment_count": len(catalog.unresolved_fragment_ids),
                "sibling_group_order_semantics": "unordered",
                "group_fragment_order_semantics": "ordered",
                "prompt_version": TREE_V2_PROMPT_VERSION,
            },
        )

    def _generate(self, request_messages: list[dict[str, str]], stage_label: str) -> str:
        try:
            structured = getattr(self.handler, "generate_structured_with_messages", None)
            if structured is not None:
                response = structured(
                    request_messages,
                    schema=ContextTreeCatalog.model_json_schema(),
                    schema_name=self.SCHEMA_NAME,
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(request_messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"{stage_label} request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError(f"{stage_label} returned an empty response")
        return response.strip()

    @classmethod
    def _repair_instruction(
        cls,
        error: Exception,
        cards: Sequence[LocalFragment],
    ) -> str:
        return (
            "Repair the ID-only catalog exactly once. Preserve every valid ID and "
            "return no summaries, unit IDs, routes, or new fragment IDs. Every "
            "supplied fragment must occur once in a group or in unresolved_fragment_ids. "
            f"Supplied fragment IDs: {[card.fragment_id for card in cards]}. "
            f"Validation detail: {str(error)[: cls.REPAIR_ERROR_CHARS]}"
        )

    @staticmethod
    def _clean_json(response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    @staticmethod
    def _duplicates(values: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        duplicates: set[str] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        return sorted(duplicates)

    @staticmethod
    def _error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        if "coverage invalid" in str(error):
            return "fragment_coverage"
        return "contract_validation"
