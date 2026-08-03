"""Two-stage global reconciliation for narrative delivery event chains.

Local extraction returns event-chain *steps*.  This module first folds steps
with the same batch-local chain identity into compact cards, asks the model for
one project-wide chain catalog, and then classifies bounded batches of local
units against that immutable catalog.  No model call owns the whole project
assignment table.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink, LocalTextUnit
from scripts.core.neologism_extraction import (
    EventChainContribution,
    NeologismMiningError,
    SourceEvidence,
    StructuredNeologismExtraction,
)


class _ModelLink(BaseModel):
    """Small model-facing link. Long free-text reasoning is intentionally absent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_chain_id: str = Field(min_length=1, max_length=200)
    relation: str = Field(pattern=r"^(primary_member|supporting_context|theme_related)$")
    confidence: float = Field(ge=0.0, le=1.0)


class _ModelAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    local_unit_id: str = Field(pattern=r"^unit_\d+$")
    assignment_state: str = Field(pattern=r"^(assigned|unassigned)$")
    links: list[_ModelLink] = Field(default_factory=list, max_length=8)


class EventChainDefinition(BaseModel):
    """One immutable chain definition produced before unit assignment."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chain_id: str = Field(min_length=1, max_length=200)
    chain_level: str = Field(default="delivery_chain", pattern=r"^delivery_chain$")
    parent_story_id: str | None = Field(default=None, max_length=200)
    event: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0)
    participants: list[str] = Field(default_factory=list, max_length=20)
    consequence: str | None = Field(default=None, max_length=500)
    evidence_unit_ids: list[str] = Field(min_length=1, max_length=5)


class LocalChainDisposition(BaseModel):
    """Exhaustive, compact accounting for one folded local chain card."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proposal_id: str = Field(min_length=1, max_length=80)
    resolution: str = Field(
        pattern=(
            r"^(merge_into|keep_as_delivery_chain|promote_to_parent_story|"
            r"reject_non_event|split_across|unresolved)$"
        )
    )
    final_chain_ids: list[str] = Field(default_factory=list, max_length=8)


class _CatalogResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_chains: list[EventChainDefinition] = Field(default_factory=list, max_length=80)
    proposal_resolutions: list[LocalChainDisposition] = Field(
        default_factory=list, max_length=500
    )


class _AssignmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignments: list[_ModelAssignment] = Field(default_factory=list, max_length=80)


class EventChainCatalogResult(BaseModel):
    """Checkpoint-safe output of the project-wide chain catalog stage."""

    model_config = ConfigDict(extra="forbid")

    final_chains: list[EventChainDefinition] = Field(default_factory=list, max_length=80)
    proposal_resolutions: list[LocalChainDisposition] = Field(
        default_factory=list, max_length=500
    )
    local_chain_cards: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    repair_count: int = Field(default=0, ge=0, le=1)
    repair_reason: str | None = None
    repair_detail: str | None = None


class EventAssignmentBatchResult(BaseModel):
    """Checkpoint-safe output for one bounded assignment batch."""

    model_config = ConfigDict(extra="forbid")

    assignments: list[DeliveryAssignment] = Field(default_factory=list, max_length=80)
    repair_count: int = Field(default=0, ge=0, le=1)
    repair_reason: str | None = None
    repair_detail: str | None = None


@dataclass(frozen=True)
class EventReconciliationResult:
    """Final in-memory contributions and their exhaustive link assignments."""

    events: list[EventChainContribution]
    delivery_assignments: list[DeliveryAssignment]
    diagnostics: dict[str, Any]


class ContextAssignmentBatchingPolicy:
    """Pack whole local units using both count and prompt-size budgets."""

    DEFAULT_MAX_UNITS = 40
    DEFAULT_MAX_SOURCE_CHARS = 12_000

    @classmethod
    def batches(
        cls,
        local_units: Sequence[LocalTextUnit],
        *,
        max_units: int = DEFAULT_MAX_UNITS,
        max_source_chars: int = DEFAULT_MAX_SOURCE_CHARS,
    ) -> list[list[LocalTextUnit]]:
        if max_units < 1 or max_source_chars < 1:
            raise ValueError("Assignment batch limits must be positive")
        batches: list[list[LocalTextUnit]] = []
        current: list[LocalTextUnit] = []
        current_chars = 0
        for unit in local_units:
            unit_chars = sum(len(str(getattr(item, "source_text", ""))) for item in unit.items)
            over_budget = current and (
                len(current) >= max_units or current_chars + unit_chars > max_source_chars
            )
            if over_budget:
                batches.append(current)
                current = []
                current_chars = 0
            current.append(unit)
            current_chars += unit_chars
        if current:
            batches.append(current)
        return batches


class ContextEventReconciliationService:
    """Build a chain catalog, then classify bounded unit batches against it."""

    MAX_UNIT_TEXT_CHARS = 900
    MAX_PROPOSALS = 500
    REPAIR_ERROR_CHARS = 1_500

    CATALOG_SYSTEM_PROMPT = """
You build the immutable project-wide catalog of narrative delivery chains from
batch-local chain cards. Return only JSON matching the supplied schema.

Each card contains steps[] from one extraction batch. Multiple steps in a card
already represent one local chain hypothesis; do not treat them as duplicate
chains. Merge or split cards only when their chronology, state transitions,
causality, branches, participants, and explicit consequences support it.

A delivery chain is a concrete narrative process. Shared characters, factions,
gods, terminology, imagery, worldbuilding, resource type, or broad theme alone
do not form a delivery chain. Parent stories may organize child chains through
parent_story_id, but parent stories never inherit delivery membership.

Return exactly one compact proposal_resolution for every proposal_id. Use
reject_non_event for a card that is only a static/theme collection. Do not omit
a card silently and do not write long rationales. Evidence is representative;
every evidence_unit_id must name a supplied unit. Write descriptive fields in
the requested description language.
"""

    ASSIGNMENT_SYSTEM_PROMPT = """
Classify only the supplied local units against the immutable final chain
catalog. Return only JSON matching the supplied schema. Never create a chain ID.

Exhaustive assignment means every supplied local_unit_id receives exactly one
record. It does NOT mean every unit belongs to a chain. `unassigned` with an
empty links array is valid and expected.

Use primary_member only for a unit that directly describes a step, branch,
state transition, or outcome in that chain. Use supporting_context for a unit
outside the process that has a direct, specific dependency on that established
chain and should receive its summary during translation. Use theme_related for
broad shared theme only; it is audit-only and is never delivered.

Context-free buttons, generic UI labels or tooltips, names, titles, and static
technology, building, modifier, trait, resource, ambient-object, or catalog
descriptions must not be forced into a chain. A static resource may receive
supporting_context from an existing chain when specific narrative evidence
supports that dependency. Shared vocabulary or theme is insufficient.

Before returning unassigned for a static unit, test whether it names a unique
artifact, aftermath state, memorial, location, project, technology, modifier,
or institution whose intended meaning depends on one catalog chain. If yes,
use supporting_context: the unit is not an event step, but its translator needs
that chain summary. For example, "Ruins of the Expedition" should support the
expedition chain when the catalog identifies those ruins as its aftermath;
"Research Speed +5%" remains unassigned. A recurring person or god without a
specific dependency is only theme_related, never supporting_context.

Decision order for every unit: (1) direct process step -> primary_member;
(2) specific dependent background/aftermath needed for translation ->
supporting_context; (3) broad thematic overlap only -> theme_related; (4) no
grounded relationship -> unassigned. Do not skip step (2) merely because the
unit is static or distant from the chain's event text.

A short option, title, button, or tooltip already grouped inside a numbered
local event unit inherits classification with that unit; do not detach it merely
because one entry is UI-like. Each link has its own relation and confidence.
Do not return source_item_ids, reasoning, prose, or new chain definitions.
"""

    def __init__(self, handler: Any):
        self.handler = handler

    def build_catalog(
        self,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        *,
        description_language: str = "en",
    ) -> EventChainCatalogResult:
        units = self._validate_units(local_units)
        cards = self.compact_local_chain_cards(units, extractions)
        payload = {
            "description_language": description_language,
            "local_chain_cards": cards,
            "valid_local_unit_ids": [unit.unit_id for unit in units],
        }
        messages = self._messages(
            self._catalog_prompt(description_language), payload
        )
        parsed, repair_count, repair_reason, repair_detail = self._parse_with_one_repair(
            messages,
            _CatalogResponse,
            "remis_event_chain_catalog",
            lambda result: self._validate_catalog(result, cards, units),
            "Event-chain catalog",
        )
        return EventChainCatalogResult(
            final_chains=parsed.final_chains,
            proposal_resolutions=parsed.proposal_resolutions,
            local_chain_cards=cards,
            repair_count=repair_count,
            repair_reason=repair_reason,
            repair_detail=repair_detail,
        )

    def assign_batch(
        self,
        local_units: Sequence[LocalTextUnit],
        catalog: EventChainCatalogResult,
        *,
        description_language: str = "en",
    ) -> EventAssignmentBatchResult:
        units = self._validate_units(local_units)
        payload = {
            "description_language": description_language,
            "final_chain_catalog": [item.model_dump() for item in catalog.final_chains],
            "required_local_unit_ids": [unit.unit_id for unit in units],
            "local_units": [self._unit_payload(unit) for unit in units],
        }
        messages = self._messages(
            self._assignment_prompt(description_language), payload
        )
        parsed, repair_count, repair_reason, repair_detail = self._parse_with_one_repair(
            messages,
            _AssignmentResponse,
            "remis_event_chain_assignments",
            lambda result: self._validate_assignment_batch(result, units, catalog),
            "Event-chain assignment",
        )
        unit_by_id = {unit.unit_id: unit for unit in units}
        assignments = [
            DeliveryAssignment(
                local_unit_id=item.local_unit_id,
                assignment_state=item.assignment_state,
                links=[DeliveryLink(**link.model_dump()) for link in item.links],
                source_item_ids=[
                    str(source.source_item_id) for source in unit_by_id[item.local_unit_id].items
                ],
            )
            for item in parsed.assignments
        ]
        return EventAssignmentBatchResult(
            assignments=assignments,
            repair_count=repair_count,
            repair_reason=repair_reason,
            repair_detail=repair_detail,
        )

    def reconcile(
        self,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        *,
        description_language: str = "en",
    ) -> EventReconciliationResult:
        """Sequential convenience path; the workflow executor parallelizes batches."""

        units = self._validate_units(local_units)
        catalog = self.build_catalog(
            units, extractions, description_language=description_language
        )
        assignment_results = [
            self.assign_batch(batch, catalog, description_language=description_language)
            for batch in ContextAssignmentBatchingPolicy.batches(units)
        ]
        return self.finalize(units, catalog, assignment_results)

    @classmethod
    def compact_local_chain_cards(
        cls,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
    ) -> list[dict[str, Any]]:
        source_to_unit = {
            str(item.source_item_id): unit.unit_id
            for unit in local_units
            for item in unit.items
        }
        cards: list[dict[str, Any]] = []
        for batch_index, extraction in enumerate(extractions):
            grouped: dict[str, list[tuple[int, EventChainContribution]]] = {}
            display_ids: dict[str, str] = {}
            for event_index, event in enumerate(extraction.events):
                normalized = event.chain_id.casefold()
                grouped.setdefault(normalized, []).append((event_index, event))
                display_ids.setdefault(normalized, event.chain_id)
            primary_by_chain = cls._primary_units_by_chain(extraction)
            for card_index, (normalized, indexed_steps) in enumerate(grouped.items()):
                ordered = sorted(indexed_steps, key=lambda item: (item[1].sequence, item[0]))
                steps = [cls._step_payload(event, source_to_unit) for _, event in ordered]
                cards.append({
                    "proposal_id": f"b{batch_index}_c{card_index}",
                    "batch_index": batch_index,
                    "local_chain_id": display_ids[normalized],
                    "steps": steps,
                    "primary_unit_ids": list(dict.fromkeys(primary_by_chain.get(normalized, []))),
                    "evidence_unit_ids": list(dict.fromkeys(
                        unit_id
                        for step in steps
                        for unit_id in step["evidence_unit_ids"]
                    )),
                })
                if len(cards) > cls.MAX_PROPOSALS:
                    raise ValueError(
                        "Folded local chain cards exceed the catalog contract limit; "
                        "refusing to silently truncate project context"
                    )
        return cards

    @staticmethod
    def _primary_units_by_chain(
        extraction: StructuredNeologismExtraction,
    ) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for assignment in extraction.delivery_assignments:
            for link in assignment.links:
                if link.relation == "primary_member":
                    result.setdefault(link.event_chain_id.casefold(), []).append(
                        assignment.local_unit_id
                    )
        return result

    @staticmethod
    def _step_payload(
        event: EventChainContribution,
        source_to_unit: dict[str, str],
    ) -> dict[str, Any]:
        evidence_units = [
            source_to_unit[item.source_item_id]
            for item in event.evidence
            if item.source_item_id in source_to_unit
        ]
        return {
            "event": event.event,
            "sequence": event.sequence,
            "participants": event.participants,
            "consequence": event.consequence,
            "boundary_status": event.boundary_status,
            "boundary_includes": event.boundary_includes,
            "boundary_excludes": event.boundary_excludes,
            "continuation_cues": event.continuation_cues,
            "evidence_unit_ids": list(dict.fromkeys(evidence_units)),
        }

    @classmethod
    def finalize(
        cls,
        local_units: Sequence[LocalTextUnit],
        catalog: EventChainCatalogResult,
        assignment_results: Sequence[EventAssignmentBatchResult],
    ) -> EventReconciliationResult:
        units = cls._validate_units(local_units)
        assignments = [
            assignment
            for result in assignment_results
            for assignment in result.assignments
        ]
        cls._validate_final_assignments(units, catalog, assignments)
        unit_by_id = {unit.unit_id: unit for unit in units}
        events = [cls._event_contribution(chain, unit_by_id) for chain in catalog.final_chains]
        repair_reasons = []
        if catalog.repair_count:
            repair_reasons.append({
                "stage": "catalog",
                "reason": catalog.repair_reason,
                "detail": catalog.repair_detail,
            })
        repair_reasons.extend(
            {
                "stage": "assignment",
                "batch_index": index,
                "reason": result.repair_reason,
                "detail": result.repair_detail,
            }
            for index, result in enumerate(assignment_results)
            if result.repair_count
        )
        return EventReconciliationResult(
            events=events,
            delivery_assignments=assignments,
            diagnostics={
                "repair_count": catalog.repair_count + sum(
                    result.repair_count for result in assignment_results
                ),
                "catalog_repair_count": catalog.repair_count,
                "assignment_repair_count": sum(
                    result.repair_count for result in assignment_results
                ),
                "assignment_batch_count": len(assignment_results),
                "repair_reasons": repair_reasons,
                "proposal_resolutions": [
                    item.model_dump() for item in catalog.proposal_resolutions
                ],
                "final_chains": [item.model_dump() for item in catalog.final_chains],
                "local_chain_cards": catalog.local_chain_cards,
            },
        )

    @classmethod
    def _validate_catalog(
        cls,
        parsed: _CatalogResponse,
        cards: Sequence[dict[str, Any]],
        units: Sequence[LocalTextUnit],
    ) -> None:
        chain_ids = [chain.chain_id for chain in parsed.final_chains]
        duplicate_chains = cls._duplicates(chain_id.casefold() for chain_id in chain_ids)
        if duplicate_chains:
            raise ValueError(f"Final chain identities must be unique: {duplicate_chains}")
        valid_chains = set(chain_ids)
        valid_units = {unit.unit_id for unit in units}
        bad_evidence = {
            unit_id
            for chain in parsed.final_chains
            for unit_id in chain.evidence_unit_ids
            if unit_id not in valid_units
        }
        if bad_evidence:
            raise ValueError(f"Catalog contains unknown evidence units: {sorted(bad_evidence)}")
        expected = {card["proposal_id"] for card in cards}
        received = [item.proposal_id for item in parsed.proposal_resolutions]
        unknown_references = {
            chain_id
            for item in parsed.proposal_resolutions
            for chain_id in item.final_chain_ids
            if chain_id not in valid_chains
        }
        missing = expected - set(received)
        unexpected = set(received) - expected
        duplicate = cls._duplicates(received)
        if missing or unexpected or duplicate or unknown_references:
            raise ValueError(
                "Local chain disposition coverage invalid: "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}, "
                f"duplicate={duplicate}, unknown_chains={sorted(unknown_references)}"
            )
        invalid_dispositions = [
            item.proposal_id
            for item in parsed.proposal_resolutions
            if (
                item.resolution in {"merge_into", "keep_as_delivery_chain"}
                and len(item.final_chain_ids) != 1
            ) or (
                item.resolution == "split_across"
                and (
                    len(item.final_chain_ids) < 2
                    or len(item.final_chain_ids) != len(set(item.final_chain_ids))
                )
            ) or (
                item.resolution in {
                    "promote_to_parent_story", "reject_non_event", "unresolved"
                }
                and item.final_chain_ids
            )
        ]
        if invalid_dispositions:
            raise ValueError(
                "Local chain dispositions conflict with their final_chain_ids: "
                f"{sorted(invalid_dispositions)}"
            )
        delivery_sources = {
            chain_id
            for item in parsed.proposal_resolutions
            if item.resolution in {
                "merge_into", "keep_as_delivery_chain", "split_across"
            }
            for chain_id in item.final_chain_ids
        }
        orphan_chains = valid_chains - delivery_sources
        if orphan_chains:
            raise ValueError(
                "Final delivery chains require a local chain-card source: "
                f"{sorted(orphan_chains)}"
            )

    @classmethod
    def _validate_assignment_batch(
        cls,
        parsed: _AssignmentResponse,
        units: Sequence[LocalTextUnit],
        catalog: EventChainCatalogResult,
    ) -> None:
        expected = {unit.unit_id for unit in units}
        received = [item.local_unit_id for item in parsed.assignments]
        missing = expected - set(received)
        unexpected = set(received) - expected
        duplicate = cls._duplicates(received)
        if missing or unexpected or duplicate:
            raise ValueError(
                "Assignment coverage invalid: "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}, duplicate={duplicate}"
            )
        valid_chains = {chain.chain_id for chain in catalog.final_chains}
        primary_by_chain: dict[str, set[str]] = {chain_id: set() for chain_id in valid_chains}
        for assignment in parsed.assignments:
            cls._validate_assignment(assignment, valid_chains)
            for link in assignment.links:
                if link.relation == "primary_member":
                    primary_by_chain[link.event_chain_id].add(assignment.local_unit_id)
        for chain in catalog.final_chains:
            required = set(chain.evidence_unit_ids) & expected
            if not required <= primary_by_chain[chain.chain_id]:
                raise ValueError(
                    f"Evidence units for {chain.chain_id} must be primary members: "
                    f"{sorted(required - primary_by_chain[chain.chain_id])}"
                )

    @classmethod
    def _validate_final_assignments(
        cls,
        units: Sequence[LocalTextUnit],
        catalog: EventChainCatalogResult,
        assignments: Sequence[DeliveryAssignment],
    ) -> None:
        expected = {unit.unit_id for unit in units}
        received = [item.local_unit_id for item in assignments]
        if set(received) != expected or cls._duplicates(received):
            raise ValueError(
                "Final assignment coverage invalid: "
                f"missing={sorted(expected - set(received))}, "
                f"unexpected={sorted(set(received) - expected)}, "
                f"duplicate={cls._duplicates(received)}"
            )
        primary = {
            (item.local_unit_id, link.event_chain_id)
            for item in assignments
            for link in item.links
            if link.relation == "primary_member"
        }
        for chain in catalog.final_chains:
            missing = [
                unit_id for unit_id in chain.evidence_unit_ids
                if (unit_id, chain.chain_id) not in primary
            ]
            if missing:
                raise ValueError(
                    f"Evidence units for {chain.chain_id} lack primary membership: {missing}"
                )

    @staticmethod
    def _validate_assignment(
        assignment: _ModelAssignment,
        valid_chains: set[str],
    ) -> None:
        if assignment.assignment_state == "unassigned" and assignment.links:
            raise ValueError("Unassigned local units must have no delivery links")
        if assignment.assignment_state == "assigned" and not assignment.links:
            raise ValueError("Assigned local units must have at least one delivery link")
        linked_chain_ids = [link.event_chain_id for link in assignment.links]
        if len(linked_chain_ids) != len(set(linked_chain_ids)):
            raise ValueError(f"Duplicate delivery links for {assignment.local_unit_id}")
        unknown = {link.event_chain_id for link in assignment.links} - valid_chains
        if unknown:
            raise ValueError(
                f"Assignment {assignment.local_unit_id} referenced unknown chains: {sorted(unknown)}"
            )

    @classmethod
    def _event_contribution(
        cls,
        chain: EventChainDefinition,
        unit_by_id: dict[str, LocalTextUnit],
    ) -> EventChainContribution:
        evidence = [
            SourceEvidence(source_item_id=str(unit_by_id[unit_id].items[0].source_item_id))
            for unit_id in chain.evidence_unit_ids
            if unit_by_id[unit_id].items
        ]
        return EventChainContribution(
            chain_id=chain.chain_id,
            chain_level="delivery_chain",
            parent_story_id=chain.parent_story_id,
            event=chain.event,
            sequence=chain.sequence,
            participants=chain.participants,
            consequence=chain.consequence,
            evidence=evidence,
        )

    def _parse_with_one_repair(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        schema_name: str,
        validator: Any,
        stage_label: str,
    ) -> tuple[Any, int, str | None, str | None]:
        response = self._generate(messages, response_model, schema_name, stage_label)
        try:
            parsed = response_model.model_validate(json.loads(self._clean_json(response)))
            validator(parsed)
            return parsed, 0, None, None
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            repair_reason = self._error_category(first_error)
            repair_detail = str(first_error)[: self.REPAIR_ERROR_CHARS]
            repair_messages = [
                *messages,
                {"role": "assistant", "content": response},
                {"role": "user", "content": self._repair_instruction(first_error)},
            ]
            repaired = self._generate(
                repair_messages, response_model, schema_name, stage_label
            )
            try:
                parsed = response_model.model_validate(json.loads(self._clean_json(repaired)))
                validator(parsed)
                return parsed, 1, repair_reason, repair_detail
            except (json.JSONDecodeError, ValidationError, ValueError) as second_error:
                detail = str(second_error)[: self.REPAIR_ERROR_CHARS]
                raise NeologismMiningError(
                    f"{stage_label} failed after one repair "
                    f"({self._error_category(second_error)}): {detail}"
                ) from second_error

    def _generate(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        schema_name: str,
        stage_label: str,
    ) -> str:
        try:
            structured = getattr(self.handler, "generate_structured_with_messages", None)
            if structured is not None:
                response = structured(
                    messages,
                    schema=response_model.model_json_schema(),
                    schema_name=schema_name,
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"{stage_label} request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError(f"{stage_label} returned an empty response")
        return response.strip()

    @classmethod
    def _unit_payload(cls, unit: LocalTextUnit) -> dict[str, Any]:
        return {
            "local_unit_id": unit.unit_id,
            "derived_unit_key": unit.unit_key.split("::", 1)[-1],
            "entries": [
                {
                    "item_key": getattr(item, "item_key", None),
                    "text": str(getattr(item, "source_text", ""))[: cls.MAX_UNIT_TEXT_CHARS],
                }
                for item in unit.items
            ],
        }

    @staticmethod
    def _validate_units(local_units: Sequence[LocalTextUnit]) -> list[LocalTextUnit]:
        units = list(local_units)
        unit_ids = [unit.unit_id for unit in units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("Global local-unit identities must be unique")
        source_ids = [str(item.source_item_id) for unit in units for item in unit.items]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("A source item must belong to exactly one global local unit")
        return units

    @staticmethod
    def _duplicates(values: Iterable[str]) -> list[str]:
        return sorted(value for value, count in Counter(values).items() if count > 1)

    @staticmethod
    def _messages(system_prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        ]

    @classmethod
    def _catalog_prompt(cls, description_language: str) -> str:
        return (
            f"{cls.CATALOG_SYSTEM_PROMPT.strip()}\n"
            f"Description language: {description_language}."
        )

    @classmethod
    def _assignment_prompt(cls, description_language: str) -> str:
        return (
            f"{cls.ASSIGNMENT_SYSTEM_PROMPT.strip()}\n"
            f"Description language: {description_language}."
        )

    @classmethod
    def _system_prompt(cls, description_language: str) -> str:
        """Human-facing full prompt example retained for the published metadata UI."""

        return (
            f"[Chain catalog]\n{cls._catalog_prompt(description_language)}\n\n"
            f"[Unit assignment]\n{cls._assignment_prompt(description_language)}"
        )

    @classmethod
    def _repair_instruction(cls, error: Exception) -> str:
        return (
            "The previous response violates the JSON or stage contract. Replace it "
            "exactly once with a complete corrected JSON object for this stage only. "
            "Preserve valid records, correct the reported fields, and return JSON only. "
            f"Validation detail: {str(error)[: cls.REPAIR_ERROR_CHARS]}"
        )

    @staticmethod
    def _clean_json(response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1 :] if newline >= 0 else ""
        return cleaned[:-3] if cleaned.endswith("```") else cleaned

    @staticmethod
    def _error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        if "coverage invalid" in str(error):
            return "coverage_validation"
        if "unknown chains" in str(error):
            return "unknown_chain"
        if "Evidence units" in str(error):
            return "evidence_membership"
        return "contract_validation"
