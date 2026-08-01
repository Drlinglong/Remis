"""Structured, source-grounded contracts for neologism mining.

This module owns the model-facing extraction boundary.  It deliberately does
not persist candidates, decide glossary state, or make translation requests.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from scripts.core.services.source_snapshot_service import normalize_relative_path, normalize_source_key


class NeologismMiningError(RuntimeError):
    """Raised when a mining response is not safe to use."""


class AnalysisScope(str, Enum):
    TERMS_ONLY = "terms_only"
    NARRATIVE_CONTEXT = "narrative_context"


TermCategory = Literal["person", "place", "faction", "concept", "technology", "other"]
EntityType = Literal[
    "person",
    "place",
    "organization/faction",
    "technology/concept",
    "item/other",
]


class SourceItem(BaseModel):
    """One source item supplied to a single model call."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_item_id: str = Field(min_length=1, max_length=240)
    relative_path: str = Field(min_length=1, max_length=500)
    item_key: Optional[str] = Field(default=None, max_length=300)
    source_order: Optional[int] = Field(default=None, ge=0)
    source_text: str = Field(min_length=1, max_length=20000)
    provenance: Literal["text_inferred"] = "text_inferred"

    @field_validator("relative_path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return normalize_relative_path(value)

    @field_validator("item_key")
    @classmethod
    def _normalize_key(cls, value: Optional[str]) -> Optional[str]:
        return normalize_source_key(value)


class SourceEvidence(BaseModel):
    """Grounded evidence returned with a contribution."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_item_id: str = Field(min_length=1, max_length=240)
    snippet: str = Field(min_length=1, max_length=2000)
    relative_path: str = ""
    item_key: Optional[str] = None
    source_order: Optional[int] = Field(default=None, ge=0)
    provenance: Literal["text_inferred"] = "text_inferred"


class TermContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    original: str = Field(min_length=1, max_length=200)
    category: TermCategory = "other"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: List[SourceEvidence] = Field(min_length=1, max_length=5)


class EntityContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=200)
    entity_type: EntityType
    description: Optional[str] = Field(default=None, max_length=1000)
    evidence: List[SourceEvidence] = Field(min_length=1, max_length=5)
    provenance: Literal["text_inferred"] = "text_inferred"


class FactContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=200)
    object: str = Field(min_length=1, max_length=500)
    evidence: List[SourceEvidence] = Field(min_length=1, max_length=5)
    provenance: Literal["text_inferred"] = "text_inferred"
    tentative: Literal[True] = True


class EventChainContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chain_id: str = Field(min_length=1, max_length=200)
    event: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0)
    participants: List[str] = Field(default_factory=list, max_length=20)
    consequence: Optional[str] = Field(default=None, max_length=500)
    evidence: List[SourceEvidence] = Field(min_length=1, max_length=5)
    provenance: Literal["text_inferred"] = "text_inferred"
    tentative: Literal[True] = True


class RelationshipContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    subject: str = Field(min_length=1, max_length=200)
    relation: str = Field(min_length=1, max_length=200)
    object: str = Field(min_length=1, max_length=200)
    evidence: List[SourceEvidence] = Field(min_length=1, max_length=5)
    provenance: Literal["text_inferred"] = "text_inferred"
    tentative: Literal[True] = True


class StructuredNeologismExtraction(BaseModel):
    """The one response contract for both analysis scopes."""

    model_config = ConfigDict(extra="forbid")

    terms: List[TermContribution] = Field(default_factory=list, max_length=100)
    entities: List[EntityContribution] = Field(default_factory=list, max_length=50)
    facts: List[FactContribution] = Field(default_factory=list, max_length=50)
    events: List[EventChainContribution] = Field(default_factory=list, max_length=50)
    relationships: List[RelationshipContribution] = Field(default_factory=list, max_length=100)


EXTRACTION_ADAPTER = TypeAdapter(StructuredNeologismExtraction)


class StructuredNeologismExtractor:
    """Make one deterministic structured extraction call for one source chunk."""

    MAX_TOTAL_CONTRIBUTIONS = 250

    SYSTEM_PROMPT = """
# Role
You are a source-grounded terminology and narrative analyst for game localization.

# Task
Analyze the supplied source items exactly once and return one JSON object. The
analysis scope is `{scope}`. In `terms_only`, fill `terms` and leave every other
array empty. In `narrative_context`, fill grounded term candidates and any
grounded source-level entities, facts, event-chain steps, and relationships.

# Game
{game_name}

# Grounding and safety rules
- Every evidence.source_item_id MUST be one of the supplied source_item_id values.
- Every evidence.snippet MUST be copied exactly from that source item's source_text.
- Every term.original and entity.name MUST occur in an evidenced source item.
- Do not invent facts, events, relationships, or entities that cannot be supported
  by an exact snippet. They are tentative model contributions, never script-derived
  or user-confirmed.
- Events belong in `events` as event-chain objects, not inside entity descriptions.
- Use only these entity_type values: "person", "place", "organization/faction",
  "technology/concept", "item/other".
- For term categories use exactly: "person", "place", "faction", "concept", "technology", or "other".
- Keep all arrays bounded and omit generic words, keys, variables, commands,
  formatting codes, and punctuation-only values.

# Output
Return only this JSON shape, with no markdown:
{{
  "terms": [{{"original":"...","category":"technology","confidence":0.9,
    "evidence":[{{"source_item_id":"...","snippet":"..."}}]}}],
  "entities": [{{"name":"...","entity_type":"technology/concept",
    "description":"...","evidence":[{{"source_item_id":"...","snippet":"..."}}],
    "provenance":"text_inferred"}}],
  "facts": [{{"subject":"...","predicate":"...","object":"...",
    "evidence":[{{"source_item_id":"...","snippet":"..."}}],
    "provenance":"text_inferred","tentative":true}}],
  "events": [{{"chain_id":"...","event":"...","sequence":0,
    "participants":[],"consequence":"...",
    "evidence":[{{"source_item_id":"...","snippet":"..."}}],
    "provenance":"text_inferred","tentative":true}}],
  "relationships": [{{"subject":"...","relation":"...","object":"...",
    "evidence":[{{"source_item_id":"...","snippet":"..."}}],
    "provenance":"text_inferred","tentative":true}}]
}}
"""

    def __init__(self, handler: Any):
        self.handler = handler
        self.logger = logging.getLogger(__name__)

    def extract(
        self,
        source_items: Sequence[SourceItem],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
        allow_legacy_term_array: bool = False,
    ) -> StructuredNeologismExtraction:
        scope = AnalysisScope(scope)
        items = self._validate_source_items(source_items)
        if not items:
            raise NeologismMiningError("Cannot extract from an empty source chunk")
        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT.format(scope=scope.value, game_name=game_name),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"scope": scope.value, "source_items": [item.model_dump() for item in items]},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]
        extraction = self._parse_with_one_repair(messages, items, allow_legacy_term_array)
        self._validate_grounding(extraction, items, scope)
        return extraction

    def extract_chunks(
        self,
        chunks: Iterable[Sequence[SourceItem]],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
    ) -> List[StructuredNeologismExtraction]:
        """Extract one response per already-read chunk; never reread or re-call a chunk."""

        return [self.extract(chunk, scope=scope, game_name=game_name) for chunk in chunks]

    def _generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            response = self.handler.generate_with_messages(messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"LLM request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError("LLM returned an empty response")
        return response.strip()

    def _parse_with_one_repair(
        self,
        messages: List[Dict[str, str]],
        source_items: Sequence[SourceItem],
        allow_legacy_term_array: bool,
    ) -> StructuredNeologismExtraction:
        response = self._generate(messages)
        try:
            return self._parse_payload(response, source_items, allow_legacy_term_array)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as first_error:
            repair_messages = messages + [
                {"role": "assistant", "content": response},
                {
                    "role": "user",
                    "content": (
                        "The previous response did not satisfy the required JSON schema or grounding rules. "
                        f"Validation error: {first_error}. Correct the previous response with one "
                        "deterministic retry. Return the corrected raw JSON array or object only; "
                        "do not add markdown or commentary."
                    ),
                },
            ]
            repaired = self._generate(repair_messages)
            try:
                return self._parse_payload(repaired, source_items, allow_legacy_term_array)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as second_error:
                self.logger.error("Structured extraction failed after one repair")
                raise NeologismMiningError(
                    "LLM returned invalid structured extraction output after one repair"
                ) from second_error

    @staticmethod
    def _parse_payload(
        response: str,
        source_items: Sequence[SourceItem],
        allow_legacy_term_array: bool,
    ) -> StructuredNeologismExtraction:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            cleaned = cleaned[first_newline + 1:] if first_newline >= 0 else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        payload = json.loads(cleaned.strip())
        if isinstance(payload, list) and allow_legacy_term_array:
            source_item = source_items[0]
            payload = {
                "terms": [
                    {
                        **term,
                        "evidence": [{
                            "source_item_id": source_item.source_item_id,
                            "snippet": source_item.source_text,
                        }],
                    }
                    for term in payload
                ]
            }
        return EXTRACTION_ADAPTER.validate_python(payload)

    @staticmethod
    def _validate_source_items(source_items: Sequence[SourceItem]) -> List[SourceItem]:
        items = list(source_items)
        ids = [item.source_item_id for item in items]
        if len(ids) != len(set(ids)):
            raise NeologismMiningError("Source item identities must be unique within one chunk")
        return items

    @classmethod
    def _validate_grounding(
        cls,
        extraction: StructuredNeologismExtraction,
        source_items: Sequence[SourceItem],
        scope: AnalysisScope,
    ) -> None:
        if scope is AnalysisScope.TERMS_ONLY and any((extraction.entities, extraction.facts, extraction.events, extraction.relationships)):
            raise NeologismMiningError("terms_only extraction returned narrative contributions")
        if sum(len(getattr(extraction, field)) for field in ("terms", "entities", "facts", "events", "relationships")) > cls.MAX_TOTAL_CONTRIBUTIONS:
            raise NeologismMiningError("Structured extraction exceeded the contribution safety limit")
        lookup = {item.source_item_id: item for item in source_items}
        contributions = [*extraction.terms, *extraction.entities, *extraction.facts, *extraction.events, *extraction.relationships]
        for contribution in contributions:
            for evidence in contribution.evidence:
                item = lookup.get(evidence.source_item_id)
                if item is None:
                    raise NeologismMiningError("Structured extraction referenced an unknown source item")
                if evidence.snippet not in item.source_text:
                    raise NeologismMiningError("Structured extraction contained an ungrounded evidence snippet")
                evidence.relative_path = item.relative_path
                evidence.item_key = item.item_key
                evidence.source_order = item.source_order
                evidence.provenance = item.provenance
            if isinstance(contribution, TermContribution) and not any(
                contribution.original.casefold() in lookup[evidence.source_item_id].source_text.casefold()
                for evidence in contribution.evidence
            ):
                raise NeologismMiningError("Structured extraction contained an ungrounded term")
            if isinstance(contribution, EntityContribution) and not any(
                contribution.name.casefold() in lookup[evidence.source_item_id].source_text.casefold()
                for evidence in contribution.evidence
            ):
                raise NeologismMiningError("Structured extraction contained an ungrounded entity")
