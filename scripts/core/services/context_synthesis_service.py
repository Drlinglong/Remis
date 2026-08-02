"""Validated, source-grounded LLM synthesis for Mod Context aggregates."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from pydantic import ValidationError

from scripts.core.neologism_extraction import NeologismMiningError
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextSourceItem,
    ContextSynthesisResponse,
    GeneratedSynthesis,
)


@dataclass(frozen=True)
class _SynthesisRequest:
    payload_json: str
    aggregate_by_alias: dict[str, ContextAggregate]
    source_id_by_alias: dict[str, str]
    evidence_aliases_by_aggregate: dict[str, frozenset[str]]


class ContextSynthesisService:
    """Make bounded structured synthesis calls with alias-grounded recovery."""

    MAX_AGGREGATES_PER_CALL = 32
    MAX_CALL_BUDGET_CHARS = 60_000
    OUTPUT_RESERVE_CHARS_PER_AGGREGATE = 1_600
    TRUNCATED_RESPONSE_MIN_CHARS = 4_096
    REPAIR_RESPONSE_EXCERPT_CHARS = 1_200
    REPAIR_ERROR_EXCERPT_CHARS = 600

    SYSTEM_PROMPT = """
You summarize source-grounded localization context. Return only JSON matching
the required schema. Make each summary concise and factual. Use only the
provided contributions and source evidence; do not add unsupported details.
Copy only the short aggregate_alias and evidence_alias values supplied in the
request. Every evidence_aliases value must identify source text used by that
summary. Entity summaries describe entities, event summaries describe ordered
event chains, and the project summary describes the project-level pattern.
"""

    LANGUAGE_NAMES = {
        "zh-cn": "Simplified Chinese",
        "zh-tw": "Traditional Chinese",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "fr": "French",
        "de": "German",
        "ru": "Russian",
        "es": "Spanish",
        "pt-br": "Brazilian Portuguese",
        "pl": "Polish",
        "tr": "Turkish",
    }

    def __init__(self, handler: Any):
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    def synthesize(
        self,
        aggregates: Iterable[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
        description_language: str = "en",
        on_batch: Callable[..., None] | None = None,
        *,
        planned_batches: list[list[ContextAggregate]] | None = None,
    ) -> list[GeneratedSynthesis]:
        aggregate_list = list(aggregates)
        if not aggregate_list:
            return []
        synthesized: list[GeneratedSynthesis] = []
        batches = planned_batches or self.plan_batches(
            aggregate_list, contributions, sources, description_language,
        )
        for batch_index, batch in enumerate(batches, start=1):
            try:
                result = self._synthesize_batch(
                    batch,
                    contributions,
                    sources,
                    description_language,
                )
            except Exception as exc:
                if on_batch is not None:
                    on_batch(batch_index, batch, success=False, error=str(exc))
                raise
            synthesized.extend(result)
            if on_batch is not None:
                on_batch(batch_index, batch, success=True)
        return synthesized

    @classmethod
    def batch_count(cls, aggregate_count: int) -> int:
        """Return the fixed-cap estimate used before payloads are available."""
        if aggregate_count <= 0:
            return 0
        return (aggregate_count + cls.MAX_AGGREGATES_PER_CALL - 1) // cls.MAX_AGGREGATES_PER_CALL

    def plan_batches(
        self,
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
        description_language: str,
    ) -> list[list[ContextAggregate]]:
        batches: list[list[ContextAggregate]] = []
        current: list[ContextAggregate] = []
        for aggregate in aggregates:
            candidate = [*current, aggregate]
            exceeds_count = len(candidate) > self.MAX_AGGREGATES_PER_CALL
            exceeds_budget = self._call_budget_chars(
                candidate,
                contributions,
                sources,
                description_language,
            ) > self.MAX_CALL_BUDGET_CHARS
            if current and (exceeds_count or exceeds_budget):
                batches.append(current)
                current = [aggregate]
            else:
                current = candidate
        if current:
            batches.append(current)
        return batches

    _plan_batches = plan_batches

    def _call_budget_chars(
        self,
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
        description_language: str,
    ) -> int:
        request = self._request_payload(aggregates, contributions, sources)
        schema_chars = len(json.dumps(ContextSynthesisResponse.model_json_schema()))
        output_reserve = len(aggregates) * self.OUTPUT_RESERVE_CHARS_PER_AGGREGATE
        return (
            len(self._system_prompt(description_language))
            + len(request.payload_json)
            + schema_chars
            + output_reserve
        )

    def _synthesize_batch(
        self,
        aggregate_list: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
        description_language: str,
    ) -> list[GeneratedSynthesis]:
        request = self._request_payload(aggregate_list, contributions, sources)
        messages = [
            {
                "role": "system",
                "content": self._system_prompt(description_language),
            },
            {"role": "user", "content": request.payload_json},
        ]
        try:
            response = self._generate(messages)
        except NeologismMiningError as error:
            if self._is_length_failure(error) and len(aggregate_list) > 1:
                return self._synthesize_split(
                    aggregate_list, contributions, sources, description_language,
                )
            raise
        try:
            parsed = self._parse_and_validate(response, request)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as first_error:
            if self._is_truncated_output(response, first_error) and len(aggregate_list) > 1:
                return self._synthesize_split(
                    aggregate_list, contributions, sources, description_language,
                )
            repair_messages = self._repair_messages(messages, response, first_error)
            try:
                repaired = self._generate(repair_messages)
            except NeologismMiningError as error:
                if self._is_length_failure(error) and len(aggregate_list) > 1:
                    return self._synthesize_split(
                        aggregate_list, contributions, sources, description_language,
                    )
                raise
            try:
                parsed = self._parse_and_validate(repaired, request)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as second_error:
                if self._is_truncated_output(repaired, second_error) and len(aggregate_list) > 1:
                    return self._synthesize_split(
                        aggregate_list, contributions, sources, description_language,
                    )
                category = self._validation_error_category(second_error)
                raise NeologismMiningError(
                    f"Context synthesis failed after one repair ({category})"
                ) from second_error
        return self._generated_syntheses(parsed, request)

    def _synthesize_split(
        self,
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
        description_language: str,
    ) -> list[GeneratedSynthesis]:
        midpoint = len(aggregates) // 2
        self.logger.warning(
            "Context synthesis hit a length boundary; retrying %d aggregates as %d and %d",
            len(aggregates),
            midpoint,
            len(aggregates) - midpoint,
        )
        return [
            *self._synthesize_batch(
                aggregates[:midpoint], contributions, sources, description_language,
            ),
            *self._synthesize_batch(
                aggregates[midpoint:], contributions, sources, description_language,
            ),
        ]

    def _repair_messages(
        self,
        messages: list[dict[str, str]],
        response: str,
        error: Exception,
    ) -> list[dict[str, str]]:
        category = self._validation_error_category(error)
        error_excerpt = str(error)[:self.REPAIR_ERROR_EXCERPT_CHARS]
        response_excerpt = response[:self.REPAIR_RESPONSE_EXCERPT_CHARS]
        instruction = (
            "Replace the invalid response exactly once. Return only valid JSON matching "
            f"the schema and alias grounding rules. Error category: {category}. "
            f"Validation detail: {error_excerpt}. Invalid response excerpt: {response_excerpt}"
        )
        return [*messages, {"role": "user", "content": instruction}]

    @classmethod
    def _is_truncated_output(cls, response: str, error: Exception) -> bool:
        if len(response) < cls.TRUNCATED_RESPONSE_MIN_CHARS:
            return False
        if isinstance(error, json.JSONDecodeError):
            stripped = response.rstrip()
            return (
                response.lstrip().startswith(("{", "[", "```"))
                and not stripped.endswith(("}", "]", "```"))
            )
        return cls._validation_error_category(error) == "aggregate_coverage"

    @staticmethod
    def _is_length_failure(error: Exception) -> bool:
        message = str(error).casefold()
        return any(marker in message for marker in (
            "finish_reason=length",
            "hit the context/output limit",
            "maximum context length",
            "truncated",
        ))

    @classmethod
    def _system_prompt(cls, description_language: str) -> str:
        language_code = description_language.strip()
        language_name = cls.LANGUAGE_NAMES.get(language_code.casefold(), language_code)
        return (
            f"{cls.SYSTEM_PROMPT.strip()}\n"
            f"Write every summary in {language_name} ({language_code}). "
            "Keep source evidence unchanged and preserve proper names when no approved localized "
            "name is provided."
        )

    @staticmethod
    def _validation_error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        message_categories = {
            "Context synthesis must return exactly one item per aggregate": "aggregate_coverage",
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

    @classmethod
    def _request_payload(
        cls,
        aggregates: list[ContextAggregate],
        contributions: dict[str, ContextContribution],
        sources: dict[str, ContextSourceItem],
    ) -> _SynthesisRequest:
        aggregate_payloads: list[dict[str, Any]] = []
        aggregate_by_alias: dict[str, ContextAggregate] = {}
        alias_by_source_id: dict[str, str] = {}
        source_id_by_alias: dict[str, str] = {}
        evidence_aliases_by_aggregate: dict[str, frozenset[str]] = {}
        for aggregate_index, aggregate in enumerate(aggregates):
            aggregate_alias = f"a{aggregate_index}"
            aggregate_by_alias[aggregate_alias] = aggregate
            contribution_payloads = []
            aggregate_sources: dict[str, dict[str, str]] = {}
            for contribution_id in aggregate.contribution_ids:
                contribution = contributions[contribution_id]
                evidence_aliases = []
                for source_id in cls._evidence_source_ids(contribution):
                    source = sources.get(source_id)
                    if source is None:
                        raise ValueError("Context contribution referenced an unknown source item")
                    evidence_alias = alias_by_source_id.get(source_id)
                    if evidence_alias is None:
                        evidence_alias = f"e{len(alias_by_source_id)}"
                        alias_by_source_id[source_id] = evidence_alias
                        source_id_by_alias[evidence_alias] = source_id
                    evidence_aliases.append(evidence_alias)
                    aggregate_sources.setdefault(evidence_alias, {
                        "evidence_alias": evidence_alias,
                        "content": source.content,
                        "source_ref": source.source_ref,
                    })
                contribution_payloads.append({
                    "contribution_type": contribution.contribution_type,
                    "details": {
                        key: value
                        for key, value in contribution.payload.items()
                        if key not in {"evidence", "provenance", "tentative"}
                    },
                    "evidence_aliases": evidence_aliases,
                })
            evidence_aliases_by_aggregate[aggregate_alias] = frozenset(aggregate_sources)
            aggregate_payloads.append({
                "aggregate_alias": aggregate_alias,
                "aggregate_type": aggregate.aggregate_type,
                "contributions": contribution_payloads,
                "source_items": list(aggregate_sources.values()),
            })
        payload_json = json.dumps(
            {"aggregates": aggregate_payloads},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return _SynthesisRequest(
            payload_json=payload_json,
            aggregate_by_alias=aggregate_by_alias,
            source_id_by_alias=source_id_by_alias,
            evidence_aliases_by_aggregate=evidence_aliases_by_aggregate,
        )

    @staticmethod
    def _evidence_source_ids(contribution: ContextContribution) -> list[str]:
        source_ids = []
        for item in contribution.payload.get("evidence", []):
            source_id = item.get("source_item_id") if isinstance(item, dict) else None
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)
        return source_ids or [contribution.source_item_id]

    @staticmethod
    def _parse_and_validate(
        response: str,
        request: _SynthesisRequest,
    ) -> ContextSynthesisResponse:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        parsed = ContextSynthesisResponse.model_validate(json.loads(cleaned.strip()))
        received = {item.aggregate_alias: item for item in parsed.syntheses}
        if (
            set(received) != set(request.aggregate_by_alias)
            or len(received) != len(parsed.syntheses)
        ):
            raise ValueError("Context synthesis must return exactly one item per aggregate")
        for item in parsed.syntheses:
            allowed_aliases = request.evidence_aliases_by_aggregate[item.aggregate_alias]
            if not set(item.evidence_aliases) <= allowed_aliases:
                raise ValueError("Context synthesis referenced evidence outside its aggregate")
        return parsed

    @staticmethod
    def _generated_syntheses(
        parsed: ContextSynthesisResponse,
        request: _SynthesisRequest,
    ) -> list[GeneratedSynthesis]:
        generated = []
        for item in parsed.syntheses:
            aggregate = request.aggregate_by_alias[item.aggregate_alias]
            generated.append(GeneratedSynthesis(
                synthesis_id=str(uuid.uuid4()),
                aggregate_id=aggregate.aggregate_id,
                context_key=aggregate.aggregate_key,
                content={
                    "summary": item.summary,
                    "evidence_source_item_ids": [
                        request.source_id_by_alias[alias]
                        for alias in item.evidence_aliases
                    ],
                },
            ))
        return generated
