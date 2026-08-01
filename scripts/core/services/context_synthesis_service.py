"""Validated, source-grounded LLM synthesis for Mod Context aggregates."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Iterable

from pydantic import ValidationError

from scripts.core.neologism_extraction import NeologismMiningError
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextSourceItem,
    ContextSynthesisResponse,
    GeneratedSynthesis,
)


class ContextSynthesisService:
    """Make one structured synthesis call and allow one deterministic repair."""

    MAX_AGGREGATES_PER_CALL = 12

    SYSTEM_PROMPT = """
You summarize source-grounded localization context. Return only JSON matching
the required schema. Make each summary concise and factual. Use only the
provided contributions and source evidence; do not add unsupported details.
Every evidence_source_item_ids value must identify source text used by that
summary. Entity summaries describe entities, event summaries describe ordered
event chains, and the project summary describes the project-level pattern.
"""

    def __init__(self, handler: Any):
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    def synthesize(
        self,
        aggregates: Iterable[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
    ) -> list[GeneratedSynthesis]:
        aggregate_list = list(aggregates)
        if not aggregate_list:
            return []
        synthesized: list[GeneratedSynthesis] = []
        for start in range(0, len(aggregate_list), self.MAX_AGGREGATES_PER_CALL):
            synthesized.extend(
                self._synthesize_batch(
                    aggregate_list[start:start + self.MAX_AGGREGATES_PER_CALL],
                    contributions,
                    sources,
                )
            )
        return synthesized

    def _synthesize_batch(
        self,
        aggregate_list: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
    ) -> list[GeneratedSynthesis]:
        request = self._request_payload(aggregate_list, contributions, sources)
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False, sort_keys=True)},
        ]
        response = self._generate(messages)
        try:
            parsed = self._parse_and_validate(response, aggregate_list, contributions, sources)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as first_error:
            repaired = self._generate(messages + [
                {"role": "assistant", "content": response},
                {
                    "role": "user",
                    "content": (
                        "Repair the previous response exactly once. Return only valid JSON matching "
                        f"the schema and grounding rules. Validation error: {first_error}"
                    ),
                },
            ])
            try:
                parsed = self._parse_and_validate(repaired, aggregate_list, contributions, sources)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as second_error:
                category = self._validation_error_category(second_error)
                raise NeologismMiningError(
                    f"Context synthesis failed after one repair ({category})"
                ) from second_error
        return [
            GeneratedSynthesis(
                synthesis_id=str(uuid.uuid4()),
                aggregate_id=item.aggregate_id,
                context_key=item.context_key,
                content={
                    "summary": item.summary,
                    "evidence_source_item_ids": item.evidence_source_item_ids,
                },
            )
            for item in parsed.syntheses
        ]

    @staticmethod
    def _validation_error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        message_categories = {
            "Context synthesis must return exactly one item per aggregate": "aggregate_coverage",
            "Context synthesis context_key does not match its aggregate": "context_key_mismatch",
            "Context contribution referenced an unknown source item": "unknown_source_item",
            "Context synthesis referenced evidence outside its aggregate": "evidence_scope",
        }
        return message_categories.get(str(error), "contract_validation")

    def _generate(self, messages: list[dict[str, str]]) -> str:
        try:
            structured_generate = getattr(
                self.handler,
                "generate_structured_with_messages",
                None,
            )
            if structured_generate is not None:
                response = structured_generate(
                    messages,
                    schema=ContextSynthesisResponse.model_json_schema(),
                    schema_name="remis_context_synthesis",
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"Context synthesis request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError("Context synthesis returned an empty response")
        return response.strip()

    @staticmethod
    def _request_payload(
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
    ) -> dict[str, Any]:
        payload = []
        for aggregate in aggregates:
            items = []
            for contribution_id in aggregate.contribution_ids:
                contribution = contributions[contribution_id]
                evidence_ids = {
                    item.get("source_item_id")
                    for item in contribution.payload.get("evidence", [])
                } or {contribution.source_item_id}
                items.append({
                    "contribution": contribution.model_dump(),
                    "source_items": [
                        {
                            "source_item_id": source.source_item_id,
                            "content": source.content,
                            "source_ref": source.source_ref,
                        }
                        for source_id in sorted(evidence_ids)
                        if (source := sources.get(source_id)) is not None
                    ],
                })
            payload.append({
                "aggregate_id": aggregate.aggregate_id,
                "context_key": aggregate.aggregate_key,
                "aggregate_type": aggregate.aggregate_type,
                "contributions": items,
            })
        return {"aggregates": payload}

    @staticmethod
    def _parse_and_validate(
        response: str,
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
    ) -> ContextSynthesisResponse:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = ContextSynthesisResponse.model_validate(json.loads(cleaned.strip()))
        expected = {aggregate.aggregate_id: aggregate for aggregate in aggregates}
        received = {item.aggregate_id: item for item in parsed.syntheses}
        if set(received) != set(expected) or len(received) != len(parsed.syntheses):
            raise ValueError("Context synthesis must return exactly one item per aggregate")
        for item in parsed.syntheses:
            aggregate = expected[item.aggregate_id]
            if item.context_key != aggregate.aggregate_key:
                raise ValueError("Context synthesis context_key does not match its aggregate")
            allowed_sources = {
                evidence.get("source_item_id")
                for contribution_id in aggregate.contribution_ids
                for evidence in contributions[contribution_id].payload.get("evidence", [])
            }
            if not allowed_sources <= set(sources):
                raise ValueError("Context contribution referenced an unknown source item")
            if not set(item.evidence_source_item_ids) <= allowed_sources:
                raise ValueError("Context synthesis referenced evidence outside its aggregate")
        return parsed
