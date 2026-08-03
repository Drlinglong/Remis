"""Structured, source-grounded contracts for neologism mining.

This module owns the model-facing extraction boundary.  It deliberately does
not persist candidates, decide glossary state, or make translation requests.
"""

from __future__ import annotations

import json
import logging
import re
from enum import Enum
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from scripts.core.context_local_units import (
    ContextLocalUnitBuilder,
    DeliveryAssignment,
    LocalTextUnit,
)
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
    """Source item reference with an optional, non-authoritative highlight."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_item_id: str = Field(min_length=1, max_length=240)
    snippet: Optional[str] = Field(default=None, max_length=2000)
    relative_path: str = ""
    item_key: Optional[str] = None
    source_order: Optional[int] = Field(default=None, ge=0)
    provenance: Literal["text_inferred"] = "text_inferred"


class TermContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    original: str = Field(min_length=1, max_length=200)
    category: TermCategory = "other"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    suggestion: Optional[str] = Field(default=None, max_length=500)
    reasoning: Optional[str] = Field(default=None, max_length=2000)
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
    delivery_assignments: List[DeliveryAssignment] = Field(default_factory=list, max_length=80)


EXTRACTION_ADAPTER = TypeAdapter(StructuredNeologismExtraction)


class StructuredNeologismExtractor:
    """Make one deterministic structured extraction call for one source chunk."""

    MAX_TOTAL_CONTRIBUTIONS = 250
    SOURCE_ALIAS_PREFIX = "source_"
    _FORMAT_TAG_RE = re.compile(r"#[A-Za-z][\w.-]*|#!|§.")
    _BACKEND_METADATA_BY_DEFINITION = {
        "SourceEvidence": ("provenance",),
        "EntityContribution": ("provenance",),
        "FactContribution": ("provenance", "tentative"),
        "EventChainContribution": ("provenance", "tentative"),
        "RelationshipContribution": ("provenance", "tentative"),
        "DeliveryAssignment": ("source_item_ids",),
    }
    _BACKEND_METADATA_BY_COLLECTION = {
        "entities": {"provenance": "text_inferred"},
        "facts": {"provenance": "text_inferred", "tentative": True},
        "events": {"provenance": "text_inferred", "tentative": True},
        "relationships": {"provenance": "text_inferred", "tentative": True},
    }

    SYSTEM_PROMPT = """
# Role
You are a source-grounded terminology and narrative analyst for game localization.

# Task
Analyze the supplied source items exactly once and return one JSON object. The
analysis scope is `{scope}`. In `terms_only`, fill `terms` and leave every other
array empty. In `narrative_context`, fill grounded term candidates and any
grounded source-level entities, facts, event-chain steps, and relationships.
For every term, you MUST include a canonical `suggestion` in {target_language}
and concise `reasoning` in {reasoning_language}. This is a one-pass extraction;
do not defer ordinary translation recommendations to a later review call.

# Game
{game_name}

# Grounding and safety rules
- Treat each supplied `item_key` as meaningful author-provided structure. Use
  key families, event numbers, and suffixes such as `.name`, `.desc`, and
  option keys to understand adjacency and event-chain roles. Do not mistake a
  localization key for prose or extract the key itself as a term.
- Treat each supplied local_text_unit only as a conservative local grouping.
  Suffix conventions vary between games and authors; similar keys, adjacency,
  comments, and file boundaries are useful clues but never prove story-chain
  membership without supporting text semantics.
- Every evidence.source_item_id MUST be one of the supplied short source aliases.
- The backend maps each valid alias to the stable source item identity. Never
  invent an alias or use an alias from another call.
- evidence.snippet is optional and is only a highlight hint. If supplied, it
  must be a short direct quote from the source item; do not use it to cite a
  paraphrase. The backend will discard an unsafe hint and derive a safe
  highlight when possible.
- Every term.original and entity.name MUST occur in an evidenced source item.
- Do not invent facts, events, relationships, or entities that cannot be supported
  by the cited source item and grounded fields. They are tentative model
  contributions, never script-derived or user-confirmed.
- Do not return `provenance` or `tentative` fields. The backend assigns this
  fixed metadata after validating the model-authored content and evidence.
- Events belong in `events` as event-chain objects, not inside entity descriptions.
- In `narrative_context`, return exactly one `delivery_assignments` item for
  every supplied local_text_unit. Use the supplied local_unit_id unchanged.
  Each assignment identifies which event-chain summaries should be delivered
  when any source item in that unit is translated. This is broader than sparse
  evidence: every unit must be assigned or explicitly marked `unassigned`.
- Every non-empty event_chain_ids value must exactly match a chain_id returned
  in this response's `events` array. Use `primary_member` for event prose,
  `supporting_context` for directly related projects/modifiers/resources, and
  `theme_related` only for broad background. Use `unassigned` with an empty
  event_chain_ids array when the batch does not support a reliable decision.
- Use only these entity_type values: "person", "place", "organization/faction",
  "technology/concept", "item/other".
- For term categories use exactly: "person", "place", "faction", "concept", "technology", or "other".
- Keep all arrays bounded and omit generic words, keys, variables, commands,
  formatting codes, and punctuation-only values.

# Output
Return only this JSON shape, with no markdown:
{{
  "terms": [{{"original":"...","category":"technology","confidence":0.9,
    "suggestion":"...","reasoning":"...",
    "evidence":[{{"source_item_id":"source_0"}}]}}],
  "entities": [{{"name":"...","entity_type":"technology/concept",
    "description":"...","evidence":[{{"source_item_id":"source_0"}}]}}],
  "facts": [{{"subject":"...","predicate":"...","object":"...",
    "evidence":[{{"source_item_id":"source_0"}}]}}],
  "events": [{{"chain_id":"...","event":"...","sequence":0,
    "participants":[],"consequence":"...",
    "evidence":[{{"source_item_id":"source_0"}}]}}],
  "relationships": [{{"subject":"...","relation":"...","object":"...",
    "evidence":[{{"source_item_id":"source_0"}}]}}],
  "delivery_assignments": [{{"local_unit_id":"unit_0",
    "event_chain_ids":["example_chain"],"role":"primary_member",
    "confidence":0.9,"reasoning":"..."}}]
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
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
    ) -> StructuredNeologismExtraction:
        scope = AnalysisScope(scope)
        items = self._validate_source_items(source_items)
        if not items:
            raise NeologismMiningError("Cannot extract from an empty source chunk")
        source_aliases = self._source_aliases(items)
        local_units = ContextLocalUnitBuilder.build(items)
        messages = [
            {
                "role": "system",
                "content": self.SYSTEM_PROMPT.format(
                    scope=scope.value,
                    game_name=game_name,
                    target_language=target_language,
                    reasoning_language=reasoning_language,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "scope": scope.value,
                        "source_items": [
                            {
                                **item.model_dump(),
                                "source_item_id": source_aliases[item.source_item_id],
                            }
                            for item in items
                        ],
                        "local_text_units": [
                            unit.prompt_payload(source_aliases) for unit in local_units
                        ] if scope is AnalysisScope.NARRATIVE_CONTEXT else [],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            },
        ]
        return self._parse_with_one_repair(
            messages,
            items,
            scope,
            allow_legacy_term_array,
            source_aliases,
            local_units,
        )

    def extract_chunks(
        self,
        chunks: Iterable[Sequence[SourceItem]],
        *,
        scope: AnalysisScope = AnalysisScope.TERMS_ONLY,
        game_name: str = "Paradox Game",
        target_language: str = "the configured target language",
        reasoning_language: str = "the configured review language",
    ) -> List[StructuredNeologismExtraction]:
        """Extract one response per already-read chunk; never reread or re-call a chunk."""

        return [
            self.extract(
                chunk,
                scope=scope,
                game_name=game_name,
                target_language=target_language,
                reasoning_language=reasoning_language,
            )
            for chunk in chunks
        ]

    def _generate(self, messages: List[Dict[str, str]]) -> str:
        try:
            structured_generate = getattr(
                self.handler,
                "generate_structured_with_messages",
                None,
            )
            if structured_generate is not None:
                response = structured_generate(
                    messages,
                    schema=self._model_response_schema(),
                    schema_name="remis_context_extraction",
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"LLM request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError("LLM returned an empty response")
        return response.strip()

    @classmethod
    def _model_response_schema(cls) -> Dict[str, Any]:
        """Return the content schema without backend-owned fixed metadata."""

        schema = StructuredNeologismExtraction.model_json_schema()
        definitions = schema.get("$defs", {})
        for definition_name, field_names in cls._BACKEND_METADATA_BY_DEFINITION.items():
            definition = definitions.get(definition_name, {})
            properties = definition.get("properties", {})
            for field_name in field_names:
                properties.pop(field_name, None)
            required = definition.get("required")
            if isinstance(required, list):
                definition["required"] = [
                    field_name for field_name in required if field_name not in field_names
                ]
        return schema

    def _parse_with_one_repair(
        self,
        messages: List[Dict[str, str]],
        source_items: Sequence[SourceItem],
        scope: AnalysisScope,
        allow_legacy_term_array: bool,
        source_aliases: Dict[str, str],
        local_units: Sequence[LocalTextUnit],
    ) -> StructuredNeologismExtraction:
        response = self._generate(messages)
        try:
            return self._parse_and_validate(
                response,
                source_items,
                scope,
                allow_legacy_term_array,
                source_aliases,
                local_units,
            )
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError, NeologismMiningError) as first_error:
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
                return self._parse_and_validate(
                    repaired,
                    source_items,
                    scope,
                    allow_legacy_term_array,
                    source_aliases,
                    local_units,
                )
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError, NeologismMiningError) as second_error:
                category = self._validation_error_category(second_error)
                self.logger.error(
                    "Structured extraction failed after one repair (%s)",
                    category,
                )
                raise NeologismMiningError(
                    "LLM returned invalid structured extraction output after one repair "
                    f"({category})"
                ) from second_error

    @staticmethod
    def _validation_error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        if isinstance(error, NeologismMiningError):
            message = str(error)
            if message.startswith("Structured extraction referenced an unknown source item"):
                return "unknown_source_item"
            if message.startswith("Structured extraction contained an ungrounded term"):
                return "ungrounded_term"
            if message.startswith("Structured extraction contained an ungrounded entity"):
                return "ungrounded_entity"
            return "grounding_validation"
        return "contract_validation"

    @classmethod
    def _source_aliases(cls, source_items: Sequence[SourceItem]) -> Dict[str, str]:
        return {
            item.source_item_id: f"{cls.SOURCE_ALIAS_PREFIX}{index}"
            for index, item in enumerate(source_items)
        }

    @classmethod
    def _normalize_evidence_snippet(
        cls,
        evidence: SourceEvidence,
        source_text: str,
        anchors: Sequence[str],
    ) -> None:
        supplied = evidence.snippet
        if supplied:
            aligned = cls._align_source_substring(supplied, source_text)
            if aligned is not None and any(
                cls._align_source_substring(str(anchor), aligned) is not None
                for anchor in anchors
                if anchor
            ):
                evidence.snippet = aligned
                return
            logging.getLogger(__name__).warning(
                "Ignored unsafe optional extraction highlight "
                "(source_item_id=%s; snippet=%s)",
                evidence.source_item_id,
                cls._bounded_detail(supplied),
            )
        evidence.snippet = cls._derive_highlight(source_text, anchors)

    @classmethod
    def _derive_highlight(cls, source_text: str, anchors: Sequence[str]) -> Optional[str]:
        for anchor in anchors:
            if not anchor:
                continue
            aligned = cls._align_source_substring(str(anchor), source_text)
            if aligned is not None and len(aligned) <= 2000:
                return aligned
        return None

    @classmethod
    def _align_source_substring(cls, candidate: str, source_text: str) -> Optional[str]:
        if candidate in source_text:
            return candidate
        candidate_folded, _ = cls._canonical_text(candidate)
        source_folded, spans = cls._canonical_text(source_text)
        if not candidate_folded:
            return None
        start = source_folded.find(candidate_folded)
        if start < 0:
            return None
        end = start + len(candidate_folded) - 1
        return source_text[spans[start][0]:spans[end][1]]

    @classmethod
    def _canonical_text(cls, value: str) -> tuple[str, list[tuple[int, int]]]:
        """Fold only formatting/typography while retaining source offsets."""

        folded: list[str] = []
        spans: list[tuple[int, int]] = []
        index = 0
        while index < len(value):
            tag = cls._FORMAT_TAG_RE.match(value, index)
            if tag:
                index = tag.end()
                continue
            char_start = index
            if value[index].isspace():
                while index < len(value) and value[index].isspace():
                    index += 1
                normalized = " "
            else:
                index += 1
                normalized = value[char_start:index]
                normalized = {
                    "'": "'",
                    "\u2018": "'",
                    "\u2019": "'",
                    '"': '"',
                    "\u201c": '"',
                    "\u201d": '"',
                    "-": "-",
                    "\u2013": "-",
                    "\u2014": "-",
                }.get(normalized, normalized)
            folded_value = normalized.casefold()
            folded.extend(folded_value)
            spans.extend((char_start, index) for _ in folded_value)
        return "".join(folded), spans

    @staticmethod
    def _bounded_detail(value: str, limit: int = 160) -> str:
        detail = " ".join(str(value).split())
        if len(detail) <= limit:
            return detail
        return detail[: limit - 1] + "…"

    @classmethod
    def _required_grounding_anchors(cls, contribution: Any) -> list[tuple[str, str]]:
        if isinstance(contribution, TermContribution):
            return [("term", contribution.original)]
        if isinstance(contribution, EntityContribution):
            return [("entity", contribution.name)]
        if isinstance(contribution, FactContribution):
            return [
                ("fact subject", contribution.subject),
                ("fact predicate", contribution.predicate),
                ("fact object", contribution.object),
            ]
        if isinstance(contribution, EventChainContribution):
            if contribution.participants:
                return [("event participant", participant) for participant in contribution.participants]
            return [("event", contribution.event)]
        return [
            ("relationship subject", contribution.subject),
            ("relationship relation", contribution.relation),
            ("relationship object", contribution.object),
        ]

    @classmethod
    def _contribution_is_grounded(
        cls,
        contribution: Any,
        evidence: Sequence[SourceEvidence],
        lookup: Dict[str, SourceItem],
    ) -> bool:
        for label, anchor in cls._required_grounding_anchors(contribution):
            if not any(
                cls._align_source_substring(anchor, lookup[item.source_item_id].source_text) is not None
                for item in evidence
            ):
                logging.getLogger(__name__).warning(
                    "Dropped extraction contribution with missing %s "
                    "(source_item_id=%s; detail=%s)",
                    label,
                    evidence[0].source_item_id if evidence else "none",
                    cls._bounded_detail(anchor),
                )
                return False
        return True

    @classmethod
    def _filter_grounded_contributions(
        cls,
        contributions: Sequence[Any],
        lookup: Dict[str, SourceItem],
    ) -> list[Any]:
        grounded: list[Any] = []
        for contribution in contributions:
            valid_evidence: list[SourceEvidence] = []
            for evidence in contribution.evidence:
                item = lookup.get(evidence.source_item_id)
                if item is None:
                    logging.getLogger(__name__).warning(
                        "Dropped unknown extraction source reference "
                        "(source_item_id=%s; detail=source alias not in batch)",
                        cls._bounded_detail(evidence.source_item_id),
                    )
                    continue
                anchors = cls._contribution_anchors(contribution)
                cls._normalize_evidence_snippet(evidence, item.source_text, anchors)
                evidence.relative_path = item.relative_path
                evidence.item_key = item.item_key
                evidence.source_order = item.source_order
                evidence.provenance = item.provenance
                valid_evidence.append(evidence)
            if valid_evidence and cls._contribution_is_grounded(contribution, valid_evidence, lookup):
                contribution.evidence = valid_evidence
                grounded.append(contribution)
            elif not valid_evidence:
                logging.getLogger(__name__).warning(
                    "Dropped extraction contribution without a valid source reference"
                )
        return grounded

    @staticmethod
    def _contribution_anchors(contribution: Any) -> list[str]:
        anchors = [
            getattr(contribution, field, None)
            for field in ("original", "name", "subject", "object", "event", "relation", "consequence")
        ]
        anchors.extend(getattr(contribution, "participants", None) or [])
        return [str(anchor) for anchor in anchors if anchor]

    def _parse_and_validate(
        self,
        response: str,
        source_items: Sequence[SourceItem],
        scope: AnalysisScope,
        allow_legacy_term_array: bool,
        source_aliases: Dict[str, str],
        local_units: Sequence[LocalTextUnit],
    ) -> StructuredNeologismExtraction:
        extraction = self._parse_payload(
            response,
            source_items,
            allow_legacy_term_array,
            source_aliases,
        )
        self._validate_grounding(extraction, source_items, scope, local_units)
        return extraction

    @classmethod
    def _parse_payload(
        cls,
        response: str,
        source_items: Sequence[SourceItem],
        allow_legacy_term_array: bool,
        source_aliases: Optional[Dict[str, str]] = None,
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
        cls._normalize_backend_metadata(payload)
        cls._remap_source_aliases(payload, source_aliases or {})
        return EXTRACTION_ADAPTER.validate_python(payload)

    @classmethod
    def _normalize_backend_metadata(cls, payload: Any) -> None:
        """Overwrite fixed metadata before validating model-authored fields."""

        if not isinstance(payload, dict):
            return
        for collection_name in ("terms", "entities", "facts", "events", "relationships"):
            contributions = payload.get(collection_name)
            if not isinstance(contributions, list):
                continue
            fixed_fields = cls._BACKEND_METADATA_BY_COLLECTION.get(collection_name, {})
            for contribution in contributions:
                if not isinstance(contribution, dict):
                    continue
                contribution.update(fixed_fields)
                evidence_items = contribution.get("evidence")
                if not isinstance(evidence_items, list):
                    continue
                for evidence in evidence_items:
                    if isinstance(evidence, dict):
                        evidence["provenance"] = "text_inferred"

    @staticmethod
    def _remap_source_aliases(payload: Any, source_aliases: Dict[str, str]) -> None:
        if not isinstance(payload, dict) or not source_aliases:
            return
        aliases = {alias: source_id for source_id, alias in source_aliases.items()}
        for field in ("terms", "entities", "facts", "events", "relationships"):
            for contribution in payload.get(field) or []:
                for evidence in contribution.get("evidence") or []:
                    source_alias = evidence.get("source_item_id")
                    if source_alias in aliases:
                        evidence["source_item_id"] = aliases[source_alias]

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
        local_units: Sequence[LocalTextUnit],
    ) -> None:
        if scope is AnalysisScope.TERMS_ONLY and any(
            (extraction.entities, extraction.facts, extraction.events, extraction.relationships)
        ):
            logging.getLogger(__name__).warning(
                "Dropped narrative contributions returned for terms_only extraction"
            )
            extraction.entities = []
            extraction.facts = []
            extraction.events = []
            extraction.relationships = []
            extraction.delivery_assignments = []
        if sum(len(getattr(extraction, field)) for field in ("terms", "entities", "facts", "events", "relationships")) > cls.MAX_TOTAL_CONTRIBUTIONS:
            raise NeologismMiningError("Structured extraction exceeded the contribution safety limit")
        lookup = {item.source_item_id: item for item in source_items}
        extraction.terms = cls._filter_grounded_contributions(extraction.terms, lookup)
        extraction.entities = cls._filter_grounded_contributions(extraction.entities, lookup)
        extraction.facts = cls._filter_grounded_contributions(extraction.facts, lookup)
        extraction.events = cls._filter_grounded_contributions(extraction.events, lookup)
        extraction.relationships = cls._filter_grounded_contributions(extraction.relationships, lookup)
        if scope is AnalysisScope.NARRATIVE_CONTEXT:
            extraction.delivery_assignments = cls._normalized_delivery_assignments(
                extraction, local_units,
            )

    @staticmethod
    def _normalized_delivery_assignments(
        extraction: StructuredNeologismExtraction,
        local_units: Sequence[LocalTextUnit],
    ) -> list[DeliveryAssignment]:
        valid_chains = {item.chain_id.casefold(): item.chain_id for item in extraction.events}
        received = {item.local_unit_id: item for item in extraction.delivery_assignments}
        normalized = []
        for unit in local_units:
            assignment = received.get(unit.unit_id)
            chains = list(dict.fromkeys(
                valid_chains[chain.casefold()]
                for chain in (assignment.event_chain_ids if assignment else [])
                if chain.casefold() in valid_chains
            ))
            role = assignment.role if assignment and chains else "unassigned"
            normalized.append(DeliveryAssignment(
                local_unit_id=unit.unit_id,
                event_chain_ids=chains,
                role=role,
                confidence=assignment.confidence if assignment else 0.0,
                reasoning=assignment.reasoning if assignment else "No model assignment returned.",
                source_item_ids=[item.source_item_id for item in unit.items],
            ))
        return normalized
