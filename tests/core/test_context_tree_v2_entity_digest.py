from __future__ import annotations

import json

from scripts.core.services.context_tree_v2_entity_digest import (
    CandidateGrade,
    CandidateKind,
    ContextTreeV2EntityDigestService,
    DigestCandidate,
    DigestLocalUnit,
)
from scripts.core.services.context_tree_v2_candidate_governance import (
    ContextTreeV2CandidateGovernanceService,
)
from scripts.core.neologism_extraction import EntityContribution, SourceEvidence, SourceItem, StructuredNeologismExtraction
from scripts.core.context_local_units import ContextLocalUnitBuilder


def _candidate(
    candidate_id: str,
    name: str,
    grade: CandidateGrade,
    unit_ids: tuple[str, ...],
    groups: tuple[str, ...],
    *,
    kind: CandidateKind = CandidateKind.ENTITY,
    description: str = "A local description.",
    aliases: tuple[str, ...] = (),
) -> DigestCandidate:
    return DigestCandidate(
        candidate_id=candidate_id,
        compact_name=name,
        local_description=description,
        aliases=aliases or (name,),
        local_unit_ids=unit_ids,
        event_group_ids=groups,
        grade=grade,
        kind=kind,
    )


def _unit(
    unit_id: str,
    order: int,
    group: str,
    text: str,
) -> DigestLocalUnit:
    return DigestLocalUnit(
        unit_id=unit_id,
        unit_order=order,
        event_group_ids=(group,),
        source_text=text,
        fragment_summary=f"Summary {unit_id}",
    )


class _FakeHandler:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_with_messages(self, messages, temperature=0.7):
        payload = json.loads(messages[1]["content"])
        self.calls.append({"messages": messages, "temperature": temperature, "payload": payload})
        focus = payload["focus_candidate"]["candidate_id"]
        sampled = [unit["unit_id"] for unit in payload["local_units"]]
        merge = None
        if focus == "entity:alpha":
            merge = {
                "target_candidate_id": "entity:alpha",
                "member_candidate_ids": ["entity:alpha", "entity:gamma"],
                "reason": "The supplied descriptions describe one referent.",
            }
        return json.dumps({
            "candidate_id": focus,
            "summary": f"Grounded digest for {focus}.",
            "evidence_unit_ids": [*sampled, "unknown-unit"],
            "semantic_merge": merge,
        })


def test_ab_candidates_call_independently_and_c_only_stays_compact():
    units = [
        _unit("unit-0", 0, "group-a", "Alpha appears in the opening."),
        _unit("unit-1", 1, "group-b", "Alpha returns with a consequence."),
        _unit("unit-2", 2, "group-c", "Beta changes the state with a named action."),
        _unit("unit-3", 3, "group-d", "Gamma is a short alias reference."),
    ]
    candidates = [
        _candidate("entity:alpha", "Alpha", CandidateGrade.B, ("unit-0", "unit-1"), ("group-a", "group-b"), aliases=("Alpha", "The Alpha")),
        _candidate("entity:beta", "Beta", CandidateGrade.A, ("unit-0", "unit-1", "unit-2"), ("group-a", "group-b", "group-c")),
        _candidate("entity:gamma", "Gamma", CandidateGrade.C, ("unit-3",), ("group-d",), description="Compact gamma description.", aliases=("Gamma", "Gamma alias")),
        _candidate("term:button", "Button", CandidateGrade.A, ("unit-0", "unit-1", "unit-2"), ("group-a", "group-b", "group-c"), kind=CandidateKind.TERM),
    ]
    handler = _FakeHandler()

    result = ContextTreeV2EntityDigestService(handler).run(
        candidates,
        units,
        project_title="Demo Project",
        human_project_summary="Human-edited project overview.",
    )

    assert [call["payload"]["focus_candidate"]["candidate_id"] for call in handler.calls] == [
        "entity:alpha", "entity:beta",
    ]
    assert all(call["temperature"] == 0.0 for call in handler.calls)
    assert [record.status for record in result.call_records] == [
        "succeeded", "succeeded", "skipped", "skipped",
    ]
    assert result.project_overview.source == "human"
    gamma_payload = handler.calls[0]["payload"]["candidate_catalog"][2]
    assert gamma_payload["compact_name"] == "Gamma"
    assert gamma_payload["local_description"] == "Compact gamma description."
    assert "aliases" not in gamma_payload
    assert "local_unit_ids" not in gamma_payload
    assert any(item.code == "c_candidate_digest_skipped" for item in result.diagnostics)


def test_governed_candidate_contract_flows_into_entity_digest():
    items = [
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events.yml",
            source_order=index,
            source_text=f"The Knight appears in scene {index}.",
        )
        for index in range(2)
    ]
    extraction = StructuredNeologismExtraction(entities=[
        EntityContribution(
            name="The Knight",
            entity_type="person",
            description="A recurring order member.",
            evidence=[SourceEvidence(source_item_id=item.source_item_id) for item in items],
        ),
    ])
    units = ContextLocalUnitBuilder.build(items)
    governed = ContextTreeV2CandidateGovernanceService().govern(
        [extraction], items, units,
    )

    result = ContextTreeV2EntityDigestService(_FakeHandler()).run(
        governed.candidates,
        [
            DigestLocalUnit(
                unit_id=unit.unit_id,
                unit_order=index,
                source_text="\n".join(item.source_text for item in unit.items),
            )
            for index, unit in enumerate(units)
        ],
    )

    assert result.digests[0].candidate_id == governed.candidates[0].candidate_id
    assert result.digests[0].digest_status == "complete"


def test_sampling_is_deterministic_and_respects_unit_char_and_group_budgets():
    units = [
        _unit(
            f"unit-{index}",
            index,
            f"group-{index}",
            ("unique high density words " if index == 6 else "ordinary ") + (f"token-{index} " * 700),
        )
        for index in range(13)
    ]
    candidate = _candidate(
        "entity:sample",
        "Sample",
        CandidateGrade.A,
        tuple(unit.unit_id for unit in units),
        tuple(f"group-{index}" for index in range(13)),
    )
    service = ContextTreeV2EntityDigestService(_FakeHandler())

    first = service.sample_units(candidate, units)
    second = service.sample_units(candidate, units)

    assert first.model_dump() == second.model_dump()
    assert first.metadata.selected_unit_count == 12
    assert first.metadata.included_char_count <= 8_000
    assert sum(len(unit.source_text) for unit in first.units) <= 8_000
    reasons = {reason for values in first.metadata.selection_reasons.values() for reason in values}
    assert "first_occurrence" in reasons
    assert "last_occurrence" in reasons
    assert "high_information_density" in reasons
    assert any(reason.startswith("event_group:") for reason in reasons)
    assert first.metadata.first_occurrence_unit_id == "unit-0"
    assert first.metadata.last_occurrence_unit_id == "unit-12"
    assert first.metadata.high_information_density_unit_id == "unit-6"
    assert first.metadata.omitted_event_group_ids


def test_semantic_merge_ids_are_validated_and_program_grade_is_recomputed():
    units = [
        _unit("unit-0", 0, "group-a", "Alpha."),
        _unit("unit-1", 1, "group-b", "Alpha again."),
        _unit("unit-2", 2, "group-c", "Gamma alias."),
    ]
    candidates = [
        _candidate("entity:alpha", "Alpha", CandidateGrade.B, ("unit-0", "unit-1"), ("group-a", "group-b")),
        _candidate("entity:gamma", "Gamma", CandidateGrade.C, ("unit-2",), ("group-c",)),
    ]
    result = ContextTreeV2EntityDigestService(_FakeHandler()).run(candidates, units)

    merge = result.semantic_merges[0]
    assert merge.target_candidate_id == "entity:alpha"
    assert merge.merged_local_unit_ids == ("unit-0", "unit-1", "unit-2")
    assert merge.local_unit_coverage == 3
    assert merge.recomputed_grade is CandidateGrade.A
    assert any(item.code == "unknown_evidence_unit_dropped" for item in result.diagnostics)


def test_generated_project_overview_is_bounded_without_a_second_model_call():
    handler = _FakeHandler()
    units = [_unit("unit-0", 0, "group-a", "source text")]
    result = ContextTreeV2EntityDigestService(handler).run(
        [_candidate("entity:alpha", "Alpha", CandidateGrade.B, ("unit-0",), ("group-a",))],
        units,
        project_title="Fallback Project",
        event_groups={"group-a": "A generated event-group summary."},
    )

    assert result.project_overview.source == "generated"
    assert result.project_overview.text.startswith("Project: Fallback Project")
    assert len(result.project_overview.text) <= 2_000
    assert len(handler.calls) == 1


class _LongEntityHandler:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate_with_messages(self, messages, temperature=0.7):
        payload = json.loads(messages[1]["content"])
        self.calls.append({"payload": payload, "temperature": temperature})
        focus = payload["focus_candidate"]["candidate_id"]
        if payload["phase"] == "final_reduction":
            evidence_ids = [
                unit_id
                for partial in payload["partial_digests"]
                for unit_id in partial["evidence_unit_ids"]
            ]
            return json.dumps({
                "candidate_id": focus,
                "summary": "Final reduction over every partial digest.",
                "evidence_unit_ids": list(dict.fromkeys(evidence_ids))[:12],
                "semantic_merge": None,
            })
        return json.dumps({
            "candidate_id": focus,
            "summary": f"Partial {payload['sampling_metadata']['digest_segment_id']}.",
            "evidence_unit_ids": [unit["unit_id"] for unit in payload["local_units"]],
            "semantic_merge": None,
        })


def test_long_entity_consumes_all_evidence_in_partials_then_final_reduction():
    units = [
        _unit(
            f"unit-{index}",
            index,
            f"group-{index // 5}",
            f"batch-{index // 5} source evidence {index} " + ("unique-token " * 80),
        ).model_copy(update={"batch_index": index // 5})
        for index in range(20)
    ]
    candidate = _candidate(
        "entity:long",
        "Long Entity",
        CandidateGrade.A,
        tuple(unit.unit_id for unit in units),
        tuple(sorted({group for unit in units for group in unit.event_group_ids})),
        description="Description from all extraction batches.",
    )
    handler = _LongEntityHandler()
    result = ContextTreeV2EntityDigestService(handler).run([candidate], units)

    digest = result.digests[0]
    assert digest.final_digest == "Final reduction over every partial digest."
    assert digest.llm_digest == digest.final_digest
    assert len(digest.partial_digests) > 1
    assert [call["payload"]["phase"] for call in handler.calls] == [
        *(["partial"] * len(digest.partial_digests)), "final_reduction",
    ]
    full_evidence = {record.unit_id: record for record in digest.full_evidence}
    assert set(full_evidence) == {unit.unit_id for unit in units}
    assert all(record.included_in_digest for record in full_evidence.values())
    assert all(record.digest_segment_id for record in full_evidence.values())
    assert all(record.digest_segment_ids for record in full_evidence.values())
    assert digest.mechanical_local_description.startswith("Description from all extraction batches.")
    final_payload = handler.calls[-1]["payload"]
    assert "local_units" not in final_payload
    assert "all_consumed_unit_ids" not in final_payload
    assert len(final_payload["partial_digests"]) == len(digest.partial_digests)
    assert any(len(partial.batch_indexes) > 1 for partial in digest.partial_digests)
    assert [partial.batch_indexes for partial in digest.partial_digests] == sorted(
        (partial.batch_indexes for partial in digest.partial_digests),
    )
    assert all(call["temperature"] == 0.0 for call in handler.calls)


class _PartialFailureHandler(_LongEntityHandler):
    def generate_with_messages(self, messages, temperature=0.7):
        payload = json.loads(messages[1]["content"])
        if (
            payload["phase"] == "partial"
            and payload["sampling_metadata"]["digest_segment_id"].endswith("0001")
        ):
            self.calls.append({"payload": payload, "temperature": temperature})
            return "not-json"
        return super().generate_with_messages(messages, temperature)


def test_partial_failure_blocks_final_digest_and_marks_result_incomplete():
    units = [
        _unit(
            f"unit-{index}",
            index,
            f"group-{index // 5}",
            f"batch-{index // 5} source evidence {index} " + ("unique-token " * 80),
        ).model_copy(update={"batch_index": index // 5})
        for index in range(20)
    ]
    candidate = _candidate(
        "entity:long-failure",
        "Long Entity Failure",
        CandidateGrade.A,
        tuple(unit.unit_id for unit in units),
        tuple(sorted({group for unit in units for group in unit.event_group_ids})),
    )
    handler = _PartialFailureHandler()
    result = ContextTreeV2EntityDigestService(handler).run([candidate], units)

    digest = result.digests[0]
    assert digest.digest_status == "incomplete"
    assert digest.final_digest == ""
    assert any(item.code == "partial_digest_incomplete" for item in result.diagnostics)
    assert [call["payload"]["phase"] for call in handler.calls].count("final_reduction") == 0
    assert any(record.phase == "final" and record.status == "skipped" for record in result.call_records)
