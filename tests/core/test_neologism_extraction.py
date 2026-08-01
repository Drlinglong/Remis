import json

import pytest

from scripts.core.neologism_extraction import (
    AnalysisScope,
    NeologismMiningError,
    SourceItem,
    StructuredNeologismExtractor,
)


class FakeHandler:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_with_messages(self, messages, temperature=0.7):
        self.calls.append((messages, temperature))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def source_item(text="The Curia Caelestis activates the Aether Engine."):
    return SourceItem(
        source_item_id="item-1",
        relative_path="events/first.yml",
        item_key="curia.activation:0",
        source_order=7,
        source_text=text,
        provenance="text_inferred",
    )


def test_narrative_context_makes_one_call_and_keeps_contributions_separate():
    handler = FakeHandler([json.dumps({
        "terms": [{
            "original": "Aether Engine",
            "category": "technology",
            "confidence": 0.91,
            "evidence": [{"source_item_id": "item-1", "snippet": "Aether Engine"}],
        }],
        "entities": [{
            "name": "Curia Caelestis",
            "entity_type": "organization/faction",
            "description": "A faction in the source.",
            "evidence": [{"source_item_id": "item-1", "snippet": "Curia Caelestis"}],
        }],
        "facts": [{
            "subject": "Curia Caelestis",
            "predicate": "activates",
            "object": "Aether Engine",
            "evidence": [{"source_item_id": "item-1", "snippet": "Curia Caelestis activates the Aether Engine."}],
        }],
        "events": [{
            "chain_id": "activation-chain",
            "event": "Aether Engine activation",
            "sequence": 0,
            "participants": ["Curia Caelestis"],
            "evidence": [{"source_item_id": "item-1", "snippet": "activates the Aether Engine"}],
        }],
        "relationships": [{
            "subject": "Curia Caelestis",
            "relation": "controls",
            "object": "Aether Engine",
            "evidence": [{"source_item_id": "item-1", "snippet": "Curia Caelestis activates the Aether Engine."}],
        }],
    })])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()], scope=AnalysisScope.NARRATIVE_CONTEXT
    )

    assert len(handler.calls) == 1
    assert handler.calls[0][1] == 0.0
    assert result.events[0].chain_id == "activation-chain"
    assert result.entities[0].entity_type == "organization/faction"
    assert result.facts[0].tentative is True
    assert result.relationships[0].provenance == "text_inferred"
    assert result.entities[0].evidence[0].relative_path == "events/first.yml"


def test_terms_only_retains_terms_and_does_not_accept_narrative_arrays():
    handler = FakeHandler([json.dumps({
        "terms": [{
            "original": "Curia Caelestis",
            "category": "faction",
            "evidence": [{"source_item_id": "item-1", "snippet": "Curia Caelestis"}],
        }],
        "entities": [],
        "facts": [],
        "events": [],
        "relationships": [],
    })])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()], scope=AnalysisScope.TERMS_ONLY
    )

    assert [term.original for term in result.terms] == ["Curia Caelestis"]
    assert not result.entities and not result.facts and not result.events and not result.relationships
    assert len(handler.calls) == 1
    assert '"scope": "terms_only"' in handler.calls[0][0][1]["content"]


def test_ungrounded_evidence_gets_one_grounding_repair_attempt():
    invalid = json.dumps({
        "terms": [{
            "original": "Hallucinated Term",
            "category": "other",
            "evidence": [{"source_item_id": "item-1", "snippet": "not in source"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    repaired = json.dumps({
        "terms": [{
            "original": "Aether Engine",
            "category": "technology",
            "evidence": [{"source_item_id": "item-1", "snippet": "Aether Engine"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid, repaired])

    result = StructuredNeologismExtractor(handler).extract([source_item()])

    assert result.terms[0].original == "Aether Engine"
    assert len(handler.calls) == 2
    assert "ungrounded evidence snippet" in handler.calls[1][0][-1]["content"]


def test_ungrounded_evidence_is_rejected_after_one_repair():
    invalid = json.dumps({
        "terms": [{
            "original": "Hallucinated Term",
            "category": "other",
            "evidence": [{"source_item_id": "item-1", "snippet": "not in source"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid, invalid])

    with pytest.raises(NeologismMiningError, match="after one repair"):
        StructuredNeologismExtractor(handler).extract([source_item()])
    assert len(handler.calls) == 2


def test_unknown_source_item_rejects_model_provenance():
    invalid = json.dumps({
        "terms": [{
            "original": "Curia Caelestis",
            "category": "faction",
            "evidence": [{"source_item_id": "other-item", "snippet": "Curia Caelestis"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid, invalid])

    with pytest.raises(NeologismMiningError, match="after one repair"):
        StructuredNeologismExtractor(handler).extract([source_item()])
    assert len(handler.calls) == 2


def test_source_identity_is_normalized_and_model_cannot_override_it():
    handler = FakeHandler([json.dumps({
        "terms": [{
            "original": "Curia Caelestis",
            "category": "faction",
            "evidence": [{
                "source_item_id": "item-1",
                "snippet": "Curia Caelestis",
                "relative_path": "forged.yml",
                "item_key": "forged",
                "source_order": 999,
                "provenance": "text_inferred",
            }],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })])

    evidence = StructuredNeologismExtractor(handler).extract([source_item()]).terms[0].evidence[0]

    assert evidence.relative_path == "events/first.yml"
    assert evidence.item_key == "curia.activation:0"
    assert evidence.source_order == 7
    assert evidence.provenance == "text_inferred"


def test_invalid_json_gets_exactly_one_repair_attempt():
    handler = FakeHandler([
        "not-json",
        json.dumps({"terms": [], "entities": [], "facts": [], "events": [], "relationships": []}),
    ])

    result = StructuredNeologismExtractor(handler).extract([source_item()])

    assert result.terms == []
    assert len(handler.calls) == 2
    assert "one deterministic retry" in handler.calls[1][0][-1]["content"]


def test_safety_limit_rejects_more_than_one_hundred_terms_after_one_repair():
    terms = [{
        "original": f"Term {index}",
        "category": "other",
        "evidence": [{"source_item_id": "item-1", "snippet": "Term"}],
    } for index in range(101)]
    source = source_item("Term " + " ".join(str(index) for index in range(101)))
    payload = json.dumps({"terms": terms, "entities": [], "facts": [], "events": [], "relationships": []})
    handler = FakeHandler([payload, payload])

    with pytest.raises(NeologismMiningError, match="after one repair"):
        StructuredNeologismExtractor(handler).extract([source])
    assert len(handler.calls) == 2


def test_absolute_source_paths_are_not_accepted_as_project_provenance():
    with pytest.raises(ValueError, match="must be relative"):
        SourceItem(
            source_item_id="item-1",
            relative_path="C:/outside.yml",
            source_text="text",
        )
