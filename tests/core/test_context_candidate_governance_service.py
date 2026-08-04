from __future__ import annotations

from typing import Iterable

from scripts.core.context_local_units import (
    ContextLocalUnitBuilder,
    DeliveryAssignment,
    DeliveryLink,
    LocalTextUnit,
)
from scripts.core.neologism_extraction import (
    EntityContribution,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.core.services.context_candidate_governance_service import (
    ContextCandidateGovernanceService,
    normalized_match_key,
)
from scripts.schemas.context_candidate import CandidateKind, CandidateTier


def _item(index: int, text: str, *, item_key: str | None = None) -> SourceItem:
    return SourceItem(
        source_item_id=f"source-{index}",
        relative_path="events/horizon.yml",
        item_key=item_key or f"story.{index}.title",
        source_order=index,
        source_text=text,
    )


def _term(
    surface: str,
    source_ids: Iterable[str],
    kind: CandidateKind,
    *,
    canonical_candidate: str | None = None,
) -> TermContribution:
    return TermContribution(
        original=surface,
        canonical_candidate=canonical_candidate,
        candidate_kind=kind,
        category="concept",
        evidence=[SourceEvidence(source_item_id=source_id) for source_id in source_ids],
    )


def _entity(surface: str, source_ids: Iterable[str]) -> EntityContribution:
    return EntityContribution(
        name=surface,
        candidate_kind=CandidateKind.ENTITY,
        entity_type="technology/concept",
        evidence=[SourceEvidence(source_item_id=source_id) for source_id in source_ids],
    )


def _extraction(
    terms: Iterable[TermContribution] = (),
    entities: Iterable[EntityContribution] = (),
) -> StructuredNeologismExtraction:
    return StructuredNeologismExtraction(terms=list(terms), entities=list(entities))


def _assignment(unit: LocalTextUnit, *chain_ids: str) -> DeliveryAssignment:
    return DeliveryAssignment(
        local_unit_id=unit.unit_id,
        assignment_state="assigned",
        links=[
            DeliveryLink(
                event_chain_id=chain_id,
                relation="primary_member",
                confidence=0.9,
            )
            for chain_id in chain_ids
        ],
    )


def _candidate(result, match_key: str):
    return next(item for item in result.candidates if item.normalized_match_key == match_key)


def test_normalization_and_article_aliases_share_one_entity_namespace():
    items = [
        _item(0, "Horizon Signal breached the wall."),
        _item(1, "The Horizon Signal returned."),
        _item(2, "THE HORIZON SIGNAL was recorded again."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    result = ContextCandidateGovernanceService().govern(
        [_extraction([
            _term("Horizon Signal", ["source-0"], CandidateKind.ENTITY),
            _term("The Horizon Signal", ["source-1"], CandidateKind.ENTITY),
        ])],
        items,
        units,
        final_delivery_assignments=[
            _assignment(units[0], "chain-a"),
            _assignment(units[1], "chain-b"),
            _assignment(units[2], "chain-b"),
        ],
        raw_extraction_checkpoints=[{"checkpoint_id": "raw-0"}],
    )

    candidate = _candidate(result, "horizon signal")
    assert normalized_match_key("  ‘ The  HORIZON Signal ’! ") == "horizon signal"
    assert normalized_match_key("The Horizon Signal", "de") == "the horizon signal"
    assert candidate.aggregate_key == "entity:horizon signal"
    assert result.aggregate_key_for_surface("The Horizon Signal") == "entity:horizon signal"
    assert candidate.aliases == ("Horizon Signal", "The Horizon Signal")
    assert candidate.canonical_display_name == "Horizon Signal"
    assert candidate.mention_count == 3
    assert candidate.source_item_coverage == 3
    assert candidate.local_unit_coverage == 3
    assert candidate.event_chain_coverage == 2
    assert candidate.policy_coverage == 3
    assert candidate.tier is CandidateTier.CORE
    assert candidate.summary_eligible is True
    assert result.policy_by_aggregate_key["entity:horizon signal"].tier is CandidateTier.CORE
    assert result.raw_extraction_checkpoints == ({"checkpoint_id": "raw-0"},)
    assert result.governed_extractions[0].terms[0].original == "Horizon Signal"
    assert result.governed_extractions[0].diagnostics["candidate_governance"]["source_aliases"] == {
        "source-0": "source_0",
        "source-1": "source_1",
        "source-2": "source_2",
    }


def test_policy_coverage_prefers_local_units_and_mentions_do_not_promote_incidental():
    items = [
        _item(0, "A named project appears. A named project appears.", item_key="story.0.title"),
        _item(1, "A named project appears.", item_key="story.0.desc"),
        _item(2, "A named project appears.", item_key="story.0.option"),
        _item(3, "A transient observation repeats transient observation.", item_key="story.1.title"),
        _item(4, "A named phrase appears once.", item_key="story.2.title"),
    ]
    units = ContextLocalUnitBuilder.build(items)
    result = ContextCandidateGovernanceService().govern(
        [_extraction([
            _term("named project", ["source-0"], CandidateKind.NAMED_PHRASE),
            _term("transient observation", ["source-3"], CandidateKind.INCIDENTAL_CONCEPT),
            _term("named phrase", ["source-4"], CandidateKind.NAMED_PHRASE),
        ])],
        items,
        units,
    )

    project = _candidate(result, "named project")
    incidental = _candidate(result, "transient observation")
    one_unit = _candidate(result, "named phrase")
    assert project.source_item_coverage == 3
    assert project.local_unit_coverage == 1
    assert project.policy_coverage == 1
    assert project.mention_count == 4
    assert project.tier is CandidateTier.SECONDARY
    assert one_unit.tier is CandidateTier.SECONDARY
    assert incidental.mention_count == 2
    assert incidental.policy_coverage == 1
    assert incidental.tier is CandidateTier.INCIDENTAL
    assert incidental.audit_only is True
    assert incidental.glossary_eligible is False

    fallback = ContextCandidateGovernanceService().govern(
        [_extraction([_term("fallback term", ["source-0"], CandidateKind.GLOSSARY_TERM)])],
        [
            _item(0, "fallback term is here."),
            _item(1, "Fallback Term is here too."),
        ],
    )
    fallback_candidate = _candidate(fallback, "fallback term")
    assert fallback_candidate.local_unit_coverage == 0
    assert fallback_candidate.source_item_coverage == 2
    assert fallback_candidate.policy_coverage == 2
    assert fallback_candidate.tier is CandidateTier.SECONDARY


def test_event_chain_coverage_comes_only_from_final_delivery_links():
    items = [
        _item(0, "Horizon Signal is described here."),
        _item(1, "An unrelated local unit is described here."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    extraction = _extraction(entities=[_entity("Horizon Signal", ["source-0"])])
    extraction.delivery_assignments = [
        _assignment(units[0], "model-chain-a"),
        _assignment(units[1], "model-chain-b"),
    ]

    result = ContextCandidateGovernanceService().govern(
        [extraction],
        items,
        units,
        final_delivery_assignments=[_assignment(units[0], "final-chain-a", "final-chain-b")],
    )
    candidate = _candidate(result, "horizon signal")

    assert candidate.source_item_coverage == 1
    assert candidate.local_unit_coverage == 1
    assert candidate.event_chain_coverage == 2
    assert candidate.event_chain_ids == ("final-chain-a", "final-chain-b")
    assert candidate.tier is CandidateTier.CORE


def test_semantic_canonical_proposals_are_suggestions_not_merges():
    item = _item(
        0,
        "The Worm appeared. Worm-in-Waiting waited. The Loop closed. "
        "Strange Loop opened. Temporal Coil spun.",
    )
    surfaces = [
        ("The Worm", CandidateKind.ENTITY, "Worm-in-Waiting"),
        ("Worm-in-Waiting", CandidateKind.NAMED_PHRASE, None),
        ("The Loop", CandidateKind.ENTITY, None),
        ("Strange Loop", CandidateKind.NAMED_PHRASE, None),
        ("Temporal Coil", CandidateKind.GLOSSARY_TERM, None),
    ]
    result = ContextCandidateGovernanceService().govern(
        [_extraction([
            _term(surface, ["source-0"], kind, canonical_candidate=proposal)
            for surface, kind, proposal in surfaces
        ])],
        [item],
        ContextLocalUnitBuilder.build([item]),
    )

    assert len(result.candidates) == 5
    assert {candidate.normalized_match_key for candidate in result.candidates} == {
        "worm",
        "worm-in-waiting",
        "loop",
        "strange loop",
        "temporal coil",
    }
    worm = _candidate(result, "worm")
    assert worm.canonical_candidate == "Worm-in-Waiting"
    assert worm.semantic_canonical_suggestions == ("Worm-in-Waiting",)
    assert worm.aggregate_key == "entity:worm"
    assert _candidate(result, "worm-in-waiting").aggregate_key == "entity:worm-in-waiting"
    assert _candidate(result, "loop").aggregate_key != _candidate(result, "strange loop").aggregate_key
    assert _candidate(result, "temporal coil").aggregate_key == "entity:temporal coil"


def test_ungrounded_evidence_does_not_extend_literal_source_coverage():
    items = [
        _item(0, "This source does not name the candidate."),
        _item(1, "Horizon Signal is named in this source."),
    ]
    result = ContextCandidateGovernanceService().govern(
        [_extraction(entities=[_entity("Horizon Signal", ["source-0"])])],
        items,
        ContextLocalUnitBuilder.build(items),
    )

    candidate = _candidate(result, "horizon signal")
    assert candidate.source_item_ids == ("source-1",)
    assert candidate.source_item_coverage == 1
    assert candidate.local_unit_coverage == 1


def test_paradox_formatting_and_name_references_preserve_grounded_coverage():
    items = [
        _item(0, "Take control of the §YColossus§!.", item_key="event.1.desc"),
        _item(1, "I am known as $NAME_Sinople$.", item_key="event.2.desc"),
    ]
    result = ContextCandidateGovernanceService().govern(
        [_extraction(terms=[
            _term("Colossus", ["source-0"], CandidateKind.GLOSSARY_TERM),
            _term("Sinople", ["source-1"], CandidateKind.ENTITY),
        ])],
        items,
        ContextLocalUnitBuilder.build(items),
    )

    assert _candidate(result, "colossus").source_item_coverage == 1
    assert _candidate(result, "sinople").source_item_coverage == 1


def test_person_role_terms_are_entities_and_secondary_entities_receive_summaries():
    items = [
        _item(0, "The Knight takes a Squire.", item_key="event.1.desc"),
        _item(1, "The Knight returns.", item_key="event.2.desc"),
    ]
    units = ContextLocalUnitBuilder.build(items)
    result = ContextCandidateGovernanceService().govern(
        [_extraction(terms=[
            TermContribution(
                original="Knight",
                candidate_kind=CandidateKind.GLOSSARY_TERM,
                category="person",
                evidence=[SourceEvidence(source_item_id="source-0")],
            ),
            TermContribution(
                original="Squire",
                candidate_kind=CandidateKind.GLOSSARY_TERM,
                category="person",
                evidence=[SourceEvidence(source_item_id="source-0")],
            ),
        ])],
        items,
        units,
    )

    knight = _candidate(result, "knight")
    squire = _candidate(result, "squire")
    assert knight.candidate_kind is CandidateKind.ENTITY
    assert knight.tier is CandidateTier.SECONDARY
    assert knight.summary_eligible is True
    assert squire.candidate_kind is CandidateKind.ENTITY
    assert squire.tier is CandidateTier.SECONDARY
    assert squire.summary_eligible is True


def test_kind_tiering_and_glossary_summary_boundaries_are_explicit():
    items = [
        _item(0, "Horizon Signal activates the Temporal Coil."),
        _item(1, "Horizon Signal activates the Temporal Coil again."),
        _item(2, "Horizon Signal activates the Temporal Coil once more."),
    ]
    units = ContextLocalUnitBuilder.build(items)
    result = ContextCandidateGovernanceService().govern(
        [_extraction(
            [_term("Temporal Coil", ["source-0"], CandidateKind.GLOSSARY_TERM)],
            [_entity("Horizon Signal", ["source-0"])],
        )],
        items,
        units,
    )

    entity = _candidate(result, "horizon signal")
    glossary = _candidate(result, "temporal coil")
    assert entity.candidate_kind is CandidateKind.ENTITY
    assert entity.tier is CandidateTier.CORE
    assert entity.summary_eligible is True
    assert glossary.candidate_kind is CandidateKind.GLOSSARY_TERM
    assert glossary.tier is CandidateTier.CORE
    assert glossary.glossary_eligible is True
    assert glossary.summary_eligible is False
    assert "entity:horizon signal" in result.synthesis_eligible_aggregate_keys
    assert "entity:temporal coil" not in result.synthesis_eligible_aggregate_keys


def test_existing_glossary_and_user_policy_can_promote_without_audit_contradiction():
    item = _item(0, "Transient Doctrine is mentioned once.")
    units = ContextLocalUnitBuilder.build([item])
    extraction = _extraction([
        _term("Transient Doctrine", ["source-0"], CandidateKind.INCIDENTAL_CONCEPT)
    ])
    service = ContextCandidateGovernanceService()

    glossary_result = service.govern(
        [extraction], [item], units, existing_glossary_matches=["The Transient Doctrine"]
    )
    glossary_candidate = _candidate(glossary_result, "transient doctrine")
    assert glossary_candidate.tier is CandidateTier.CORE
    assert glossary_candidate.audit_only is False
    assert glossary_candidate.glossary_eligible is True
    assert glossary_candidate.summary_eligible is False
    assert "existing_glossary_match" in glossary_candidate.promotion_reasons

    confirmed_result = service.govern(
        [extraction], [item], units, user_confirmed_match_keys=["Transient Doctrine"]
    )
    confirmed = _candidate(confirmed_result, "transient doctrine")
    assert confirmed.tier is CandidateTier.CORE
    assert confirmed.audit_only is False
    assert confirmed.glossary_eligible is True

    override_result = service.govern(
        [extraction],
        [item],
        units,
        user_policy_overrides={
            "Transient Doctrine": {
                "candidate_kind": "entity",
                "tier": "core",
                "summary_eligible": True,
                "glossary_eligible": True,
                "audit_only": False,
            }
        },
    )
    overridden = _candidate(override_result, "transient doctrine")
    assert overridden.candidate_kind is CandidateKind.ENTITY
    assert overridden.tier is CandidateTier.CORE
    assert overridden.summary_eligible is True
    assert overridden.glossary_eligible is True
    assert overridden.audit_only is False

    audit_override_result = service.govern(
        [extraction],
        [item],
        units,
        user_policy_overrides={
            "Transient Doctrine": {"tier": "core", "audit_only": True}
        },
    )
    audit_override = _candidate(audit_override_result, "transient doctrine")
    assert audit_override.tier is CandidateTier.CORE
    assert audit_override.audit_only is True
    assert "user_policy_audit_only" in audit_override.promotion_reasons
