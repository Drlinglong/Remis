"""Global, validated reconciliation of locally proposed delivery event chains.

The extraction pass intentionally works on bounded chunks.  This service is a
separate second pass: it sees stable project-wide local units and the compact
event proposals from every extraction chunk, then decides the final delivery
chains and the membership of *every* local unit.  It does not persist anything
or decide how a caller schedules the model request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scripts.core.context_local_units import DeliveryAssignment, DeliveryLink, LocalTextUnit
from scripts.core.neologism_extraction import (
    EventChainContribution,
    NeologismMiningError,
    SourceEvidence,
    StructuredNeologismExtraction,
)


class _ModelAssignment(BaseModel):
    """Model-facing assignment; source IDs are intentionally backend-owned."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    local_unit_id: str = Field(pattern=r"^unit_\d+$")
    assignment_state: str = Field(pattern=r"^(assigned|unassigned)$")
    links: list["_ModelLink"] = Field(default_factory=list, max_length=8)


class _ModelLink(BaseModel):
    """Strict model-facing form; persisted links allow optional rationale."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_chain_id: str = Field(min_length=1, max_length=200)
    relation: str = Field(pattern=r"^(primary_member|supporting_context|theme_related)$")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(min_length=1, max_length=500)


class _FinalChainResponse(BaseModel):
    """Model-facing final delivery-chain shape without backend evidence IDs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    chain_id: str = Field(min_length=1, max_length=200)
    chain_level: str = Field(default="delivery_chain", pattern=r"^delivery_chain$")
    parent_story_id: str | None = Field(default=None, max_length=200)
    event: str = Field(min_length=1, max_length=500)
    sequence: int = Field(ge=0)
    participants: list[str] = Field(default_factory=list, max_length=20)
    consequence: str | None = Field(default=None, max_length=500)
    evidence_unit_ids: list[str] = Field(min_length=1, max_length=5)


class _ProposalResolution(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    proposal_id: str = Field(min_length=1, max_length=80)
    resolution: str = Field(
        pattern=r"^(merge_into|keep_separate|split_required|parent_story_only|unresolved)$"
    )
    final_chain_ids: list[str] = Field(default_factory=list, max_length=8)


class _ReconciliationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_chains: list[_FinalChainResponse] = Field(default_factory=list, max_length=80)
    assignments: list[_ModelAssignment] = Field(default_factory=list, max_length=500)
    proposal_resolutions: list[_ProposalResolution] = Field(default_factory=list, max_length=500)


@dataclass(frozen=True)
class EventReconciliationResult:
    """Final in-memory contributions and their exhaustive link assignments."""

    events: list[EventChainContribution]
    delivery_assignments: list[DeliveryAssignment]
    diagnostics: dict[str, Any]


class ContextEventReconciliationService:
    """Call an LLM once (plus at most one repair) to reconcile event chains."""

    MAX_UNIT_TEXT_CHARS = 900
    MAX_PROPOSALS = 500
    REPAIR_ERROR_CHARS = 1_200

    SYSTEM_PROMPT = """
You reconcile localization narrative event proposals into final *delivery
chains*. Return only valid JSON matching the supplied schema.

First decide clear, narrow candidate delivery-chain boundaries. A delivery
chain is a coherent causal or narrative sequence whose summary should be sent
to translations of its formal members. Do not flatten unrelated scenes into a
single chain merely because they share a faction, god, ruler, variable, broad
theme, or similar wording.

Parent stories can organize several child scenes, but they are NOT automatic
delivery chains. Record a broader story only as a delivery chain's optional
parent_story_id. It is an organizational label and never creates inherited
delivery membership.

Then return exactly one assignment for every supplied local_unit_id. Use:
- primary_member: the unit is part of the chain's actual event process; its
  translation receives the chain summary.
- supporting_context: the unit is outside the process, but needs that chain's
  background for translation; this is directional and does not merge chains.
- theme_related: shared theme only; it is archival/audit information and does
  not cause automatic summary delivery.
- unassigned: no meaningful link. It must have assignment_state=unassigned
  and an empty links array.

An assigned unit must have at least one link. Each link may use a different
relation. Evidence is representative, but every evidence_unit_id MUST be a
primary_member of that same chain. Write event, consequence, and reasoning in
the requested description language. The proposal cards are leads, not proof:
resolve chunk boundaries using the supplied unit text and keys.

Every final chain has chain_level=delivery_chain. Return exactly one
proposal_resolution for every supplied proposal_id. A proposal may merge,
remain separate, require a split, be parent-story-only, or remain unresolved.
Every final_chain_id referenced by a resolution must exist.
"""

    def __init__(self, handler: Any):
        self.handler = handler

    def reconcile(
        self,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        *,
        description_language: str = "en",
    ) -> EventReconciliationResult:
        """Return validated final chains and exactly one assignment per unit."""

        units = self._validate_units(local_units)
        payload = self._request_payload(units, extractions, description_language)
        proposal_ids = [item["proposal_id"] for item in payload["local_event_proposals"]]
        messages = [
            {"role": "system", "content": self._system_prompt(description_language)},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, sort_keys=True)},
        ]
        response = self._generate(messages)
        try:
            parsed = self._parse_and_validate(response, units, proposal_ids)
            repair_count = 0
        except (json.JSONDecodeError, ValidationError, ValueError) as first_error:
            repair_messages = [
                *messages,
                {"role": "assistant", "content": response},
                {"role": "user", "content": self._repair_instruction(first_error)},
            ]
            repaired = self._generate(repair_messages)
            try:
                parsed = self._parse_and_validate(repaired, units, proposal_ids)
                repair_count = 1
            except (json.JSONDecodeError, ValidationError, ValueError) as second_error:
                raise NeologismMiningError(
                    "Event-chain reconciliation failed after one repair "
                    f"({self._error_category(second_error)})"
                ) from second_error
        return self._result(parsed, units, repair_count=repair_count)

    @staticmethod
    def _validate_units(local_units: Sequence[LocalTextUnit]) -> list[LocalTextUnit]:
        units = list(local_units)
        unit_ids = [unit.unit_id for unit in units]
        if len(unit_ids) != len(set(unit_ids)):
            raise ValueError("Global local-unit identities must be unique")
        source_ids = [
            str(item.source_item_id)
            for unit in units
            for item in unit.items
        ]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("A source item must belong to exactly one global local unit")
        return units

    @classmethod
    def _request_payload(
        cls,
        local_units: Sequence[LocalTextUnit],
        extractions: Sequence[StructuredNeologismExtraction],
        description_language: str,
    ) -> dict[str, Any]:
        source_to_unit = {
            str(item.source_item_id): unit.unit_id
            for unit in local_units
            for item in unit.items
        }
        return {
            "description_language": description_language,
            "local_units": [cls._unit_payload(unit) for unit in local_units],
            "local_event_proposals": cls._proposal_cards(extractions, source_to_unit),
        }

    @classmethod
    def _unit_payload(cls, unit: LocalTextUnit) -> dict[str, Any]:
        entries = []
        for item in unit.items:
            text = str(getattr(item, "source_text", ""))
            entries.append({
                "item_key": getattr(item, "item_key", None),
                "text": text[:cls.MAX_UNIT_TEXT_CHARS],
            })
        return {
            "local_unit_id": unit.unit_id,
            "derived_unit_key": unit.unit_key.split("::", 1)[-1],
            "entries": entries,
        }

    @classmethod
    def _proposal_cards(
        cls,
        extractions: Sequence[StructuredNeologismExtraction],
        source_to_unit: dict[str, str],
    ) -> list[dict[str, Any]]:
        proposals = []
        for batch_index, extraction in enumerate(extractions):
            assignment_by_chain: dict[str, list[str]] = {}
            for assignment in extraction.delivery_assignments:
                for link in assignment.links:
                    if link.relation == "primary_member":
                        assignment_by_chain.setdefault(link.event_chain_id.casefold(), []).append(
                            assignment.local_unit_id
                        )
            for event_index, event in enumerate(extraction.events):
                evidence_units = [
                    source_to_unit[evidence.source_item_id]
                    for evidence in event.evidence
                    if evidence.source_item_id in source_to_unit
                ]
                proposals.append({
                    "proposal_id": f"b{batch_index}_e{event_index}",
                    "local_chain_id": event.chain_id,
                    "event": event.event,
                    "sequence": event.sequence,
                    "participants": event.participants,
                    "consequence": event.consequence,
                    "primary_unit_ids": list(dict.fromkeys(
                        assignment_by_chain.get(event.chain_id.casefold(), [])
                    )),
                    "evidence_unit_ids": list(dict.fromkeys(evidence_units)),
                })
                if len(proposals) >= cls.MAX_PROPOSALS:
                    return proposals
        return proposals

    def _generate(self, messages: list[dict[str, str]]) -> str:
        try:
            structured_generate = getattr(self.handler, "generate_structured_with_messages", None)
            if structured_generate is not None:
                response = structured_generate(
                    messages,
                    schema=_ReconciliationResponse.model_json_schema(),
                    schema_name="remis_event_chain_reconciliation",
                    temperature=0.0,
                )
            else:
                response = self.handler.generate_with_messages(messages, temperature=0.0)
        except Exception as exc:
            raise NeologismMiningError(f"Event-chain reconciliation request failed: {exc}") from exc
        if not response or not response.strip():
            raise NeologismMiningError("Event-chain reconciliation returned an empty response")
        return response.strip()

    @classmethod
    def _parse_and_validate(
        cls,
        response: str,
        local_units: Sequence[LocalTextUnit],
        proposal_ids: Sequence[str],
    ) -> _ReconciliationResponse:
        parsed = _ReconciliationResponse.model_validate(json.loads(cls._clean_json(response)))
        expected_ids = {unit.unit_id for unit in local_units}
        received_ids = [assignment.local_unit_id for assignment in parsed.assignments]
        unknown_ids = set(received_ids) - expected_ids
        missing_ids = expected_ids - set(received_ids)
        duplicate_ids = {item for item in received_ids if received_ids.count(item) > 1}
        if unknown_ids or missing_ids or duplicate_ids:
            raise ValueError(
                "Assignment coverage invalid: "
                f"missing={sorted(missing_ids)}, unexpected={sorted(unknown_ids)}, "
                f"duplicate={sorted(duplicate_ids)}"
            )
        chain_ids = [chain.chain_id for chain in parsed.final_chains]
        duplicate_chains = {item for item in chain_ids if chain_ids.count(item) > 1}
        if duplicate_chains:
            raise ValueError(f"Final chain identities must be unique: {sorted(duplicate_chains)}")
        valid_chains = set(chain_ids)
        cls._validate_proposal_resolutions(parsed, proposal_ids, valid_chains)
        primary_units_by_chain: dict[str, set[str]] = {chain_id: set() for chain_id in valid_chains}
        for assignment in parsed.assignments:
            cls._validate_assignment(assignment, valid_chains)
            for link in assignment.links:
                if link.relation == "primary_member":
                    primary_units_by_chain[link.event_chain_id].add(assignment.local_unit_id)
        for chain in parsed.final_chains:
            evidence = set(chain.evidence_unit_ids)
            if not evidence <= primary_units_by_chain[chain.chain_id]:
                raise ValueError(
                    f"Evidence units for {chain.chain_id} must be primary members of that chain"
                )
        return parsed

    @staticmethod
    def _validate_proposal_resolutions(
        parsed: _ReconciliationResponse,
        proposal_ids: Sequence[str],
        valid_chains: set[str],
    ) -> None:
        expected = set(proposal_ids)
        received = [item.proposal_id for item in parsed.proposal_resolutions]
        missing = expected - set(received)
        unexpected = set(received) - expected
        duplicate = {item for item in received if received.count(item) > 1}
        unknown_chains = {
            chain_id
            for item in parsed.proposal_resolutions
            for chain_id in item.final_chain_ids
            if chain_id not in valid_chains
        }
        if missing or unexpected or duplicate or unknown_chains:
            raise ValueError(
                "Proposal resolution coverage invalid: "
                f"missing={sorted(missing)}, unexpected={sorted(unexpected)}, "
                f"duplicate={sorted(duplicate)}, unknown_chains={sorted(unknown_chains)}"
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
        links = [(link.event_chain_id, link.relation) for link in assignment.links]
        if len(links) != len(set(links)):
            raise ValueError(f"Duplicate delivery links for {assignment.local_unit_id}")
        unknown_chains = {link.event_chain_id for link in assignment.links} - valid_chains
        if unknown_chains:
            raise ValueError(
                f"Assignment {assignment.local_unit_id} referenced unknown chains: "
                f"{sorted(unknown_chains)}"
            )

    @staticmethod
    def _clean_json(response: str) -> str:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            newline = cleaned.find("\n")
            cleaned = cleaned[newline + 1:] if newline >= 0 else ""
        return cleaned[:-3] if cleaned.endswith("```") else cleaned

    @classmethod
    def _result(
        cls,
        parsed: _ReconciliationResponse,
        local_units: Sequence[LocalTextUnit],
        *,
        repair_count: int,
    ) -> EventReconciliationResult:
        unit_by_id = {unit.unit_id: unit for unit in local_units}
        assignments = [
            DeliveryAssignment(
                local_unit_id=assignment.local_unit_id,
                assignment_state=assignment.assignment_state,
                links=[DeliveryLink(**link.model_dump()) for link in assignment.links],
                source_item_ids=[
                    str(item.source_item_id)
                    for item in unit_by_id[assignment.local_unit_id].items
                ],
            )
            for assignment in parsed.assignments
        ]
        events = []
        for chain in parsed.final_chains:
            evidence = [
                SourceEvidence(source_item_id=str(unit_by_id[unit_id].items[0].source_item_id))
                for unit_id in chain.evidence_unit_ids
                if unit_by_id[unit_id].items
            ]
            events.append(EventChainContribution(
                chain_id=chain.chain_id,
                chain_level="delivery_chain",
                parent_story_id=chain.parent_story_id,
                event=chain.event,
                sequence=chain.sequence,
                participants=chain.participants,
                consequence=chain.consequence,
                evidence=evidence,
            ))
        return EventReconciliationResult(
            events=events,
            delivery_assignments=assignments,
            diagnostics=cls._diagnostics(parsed, repair_count),
        )

    @staticmethod
    def _diagnostics(parsed: _ReconciliationResponse, repair_count: int) -> dict[str, Any]:
        return {
            "repair_count": repair_count,
            "proposal_resolutions": [item.model_dump() for item in parsed.proposal_resolutions],
            "final_chains": [chain.model_dump() for chain in parsed.final_chains],
        }

    @classmethod
    def _system_prompt(cls, description_language: str) -> str:
        return (
            f"{cls.SYSTEM_PROMPT.strip()}\n"
            f"Description language: {description_language}."
        )

    @classmethod
    def _repair_instruction(cls, error: Exception) -> str:
        return (
            "The previous response violates the JSON or reconciliation contract. "
            "Replace it exactly once with a complete corrected JSON object. "
            "Keep every valid assignment, but correct the reported issue. "
            "Return JSON only. Validation detail: "
            f"{str(error)[:cls.REPAIR_ERROR_CHARS]}"
        )

    @staticmethod
    def _error_category(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return "invalid_json"
        if isinstance(error, ValidationError):
            return "schema_validation"
        if "Assignment coverage invalid" in str(error):
            return "assignment_coverage"
        if "unknown chains" in str(error):
            return "unknown_chain"
        if "Evidence units" in str(error):
            return "evidence_membership"
        return "contract_validation"
