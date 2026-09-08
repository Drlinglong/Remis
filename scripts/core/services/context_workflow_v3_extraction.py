"""Three-axis extraction stage for the lightweight workflow v3."""

from __future__ import annotations

from typing import Any, Sequence

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import AnalysisScope, SourceItem
from scripts.core.prompts.context_tree_v2_prompt import messages
from scripts.core.prompts.context_workflow_v3_prompt import (
    workflow_v3_extraction_prompt,
)
from scripts.core.services.context_tree_v2_contract import ChunkEdgeMetadata
from scripts.core.services.context_tree_v2_extraction_service import (
    ContextTreeV2ExtractionService,
)


class ContextWorkflowV3ExtractionService(ContextTreeV2ExtractionService):
    """Reuse Tree v2 parsing/repair while replacing its model instructions."""

    SCHEMA_NAME = "remis_context_workflow_v3_extraction"

    @classmethod
    def _parse_response(
        cls,
        response: str,
        source_items: Sequence[SourceItem],
        source_aliases: dict[str, str],
    ) -> Any:
        """Keep V3's independent term/entity axes, never legacy narratives."""

        extraction = super()._parse_response(
            response, source_items, source_aliases,
        )
        discarded = {
            field: len(getattr(extraction, field))
            for field in ("facts", "events", "relationships")
            if getattr(extraction, field)
        }
        extraction.facts = []
        extraction.events = []
        extraction.relationships = []
        extraction.diagnostics = {
            **extraction.diagnostics,
            "workflow_v3_legacy_fields_discarded": discarded,
        }
        return extraction

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
        source_aliases: dict[str, str],
        description_language: str | None = None,
    ) -> list[dict[str, str]]:
        del scope
        payload = {
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
            ],
            "core_unit_ids": [unit.unit_id for unit in core_units],
            "chunk_edge_metadata": metadata.model_dump(),
        }
        return messages(
            workflow_v3_extraction_prompt(
                game_name=game_name,
                target_language=target_language,
                reasoning_language=reasoning_language,
                description_language=description_language or reasoning_language,
            ),
            payload,
        )


__all__ = ["ContextWorkflowV3ExtractionService"]
