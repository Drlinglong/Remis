"""Single global lead for workflow v3 event grouping and Mod context."""

from __future__ import annotations

import json
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.core.neologism_extraction import NeologismMiningError
from scripts.core.prompts.context_tree_v2_prompt import messages
from scripts.core.prompts.context_workflow_v3_prompt import workflow_v3_catalog_prompt
from scripts.core.services.context_tree_v2_catalog_service import (
    ContextTreeV2CatalogService,
)
from scripts.core.services.context_tree_v2_contract import (
    ChunkEdgeMetadata,
    ContextTreeCatalog,
    LocalFragment,
    TreeCatalogResult,
    TreeGroup,
    TreeStory,
)


class WorkflowV3CatalogEnvelope(BaseModel):
    """ID-owned global relations plus one bounded user-facing root summary."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    stories: list[TreeStory] = Field(default_factory=list, max_length=80)
    groups: list[TreeGroup] = Field(default_factory=list, max_length=80)
    unresolved_fragment_ids: list[str] = Field(default_factory=list, max_length=80)
    universal_translation_context: str = Field(min_length=50, max_length=100)

    def catalog(self) -> ContextTreeCatalog:
        return ContextTreeCatalog(
            stories=self.stories,
            groups=self.groups,
            unresolved_fragment_ids=self.unresolved_fragment_ids,
        )


class ContextWorkflowV3CatalogService(ContextTreeV2CatalogService):
    """Run one global model call without letting it rewrite local findings."""

    SCHEMA_NAME = "remis_context_workflow_v3_catalog"

    def build_catalog(
        self,
        fragment_cards: Sequence[LocalFragment],
        *,
        chunk_edge_metadata: Sequence[ChunkEdgeMetadata] = (),
        description_language: str = "zh-CN",
    ) -> TreeCatalogResult:
        cards = self._normalize_cards(fragment_cards)
        if not cards:
            return TreeCatalogResult(
                catalog=ContextTreeCatalog(),
                diagnostics={
                    "model_call_count": 0,
                    "fragment_count": 0,
                    "universal_translation_context": "",
                    "workflow_version": "context-workflow-v3",
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
        request_messages = messages(
            workflow_v3_catalog_prompt(description_language), payload,
        )
        response = self._generate_v3(request_messages, "Workflow v3 global catalog")
        try:
            envelope = self._parse_v3(response, cards)
            return self._result_v3(envelope, cards, repair_count=0)
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            repair_messages = [
                *request_messages,
                {"role": "assistant", "content": response},
                {"role": "user", "content": self._repair_v3(first_error, cards, description_language)},
            ]
            repaired = self._generate_v3(
                repair_messages, "Workflow v3 global catalog repair",
            )
            try:
                envelope = self._parse_v3(repaired, cards)
            except (json.JSONDecodeError, ValidationError, ValueError) as second_error:
                raise NeologismMiningError(
                    "Workflow v3 catalog failed after one repair "
                    f"({self._error_category(second_error)}): "
                    f"{str(second_error)[: self.REPAIR_ERROR_CHARS]}"
                ) from second_error
            return self._result_v3(
                envelope,
                cards,
                repair_count=1,
                repair_reason=self._error_category(first_error),
                repair_detail=str(first_error)[: self.REPAIR_ERROR_CHARS],
            )

    def _generate_v3(self, request_messages: list[dict[str, str]], label: str) -> str:
        try:
            structured = getattr(self.handler, "generate_structured_with_messages", None)
            if structured is not None:
                response = structured(
                    request_messages,
                    schema=WorkflowV3CatalogEnvelope.model_json_schema(),
                    schema_name=self.SCHEMA_NAME,
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(
                    request_messages, temperature=0.0,
                )
        except Exception as exc:
            raise NeologismMiningError(f"{label} request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError(f"{label} returned an empty response")
        return response.strip()

    @classmethod
    def _parse_v3(
        cls, response: str, cards: Sequence[LocalFragment],
    ) -> WorkflowV3CatalogEnvelope:
        envelope = WorkflowV3CatalogEnvelope.model_validate_json(
            cls._clean_json(response),
        )
        cls.validate_catalog(envelope.catalog(), cards)
        return envelope

    @staticmethod
    def _result_v3(
        envelope: WorkflowV3CatalogEnvelope,
        cards: Sequence[LocalFragment],
        *,
        repair_count: int,
        repair_reason: str | None = None,
        repair_detail: str | None = None,
    ) -> TreeCatalogResult:
        catalog = envelope.catalog()
        context_length = len(envelope.universal_translation_context)
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
                "universal_translation_context": envelope.universal_translation_context,
                "universal_translation_context_length": context_length,
                "universal_translation_context_target_met": 50 <= context_length <= 100,
                "workflow_version": "context-workflow-v3",
            },
        )

    @classmethod
    def _repair_v3(
        cls, error: Exception, cards: Sequence[LocalFragment], description_language: str,
    ) -> str:
        return (
            "Repair the workflow v3 response exactly once. Return the full JSON "
            f"envelope including a 50-100-character universal_translation_context in {description_language}. "
            "Every supplied fragment ID must occur exactly once in one group or in "
            "unresolved_fragment_ids; never invent or omit an ID. "
            f"Supplied fragment IDs: {[card.fragment_id for card in cards]}. "
            f"Validation detail: {str(error)[: cls.REPAIR_ERROR_CHARS]}"
        )


__all__ = ["ContextWorkflowV3CatalogService", "WorkflowV3CatalogEnvelope"]
