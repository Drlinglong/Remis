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


class StructuredFakeHandler:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def generate_structured_with_messages(
        self,
        messages,
        *,
        schema,
        schema_name,
        temperature,
    ):
        self.calls.append((messages, schema, schema_name, temperature))
        return self.response


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
            "evidence": [{"source_item_id": "item-1", "snippet": "A model summary that is not source text"}],
        }],
        "facts": [{
            "subject": "Curia Caelestis",
            "predicate": "activates",
            "object": "Aether Engine",
            "evidence": [{"source_item_id": "item-1", "snippet": "A paraphrase that is not source text"}],
        }],
        "events": [{
            "chain_id": "activation-chain",
            "event": "Aether Engine activation",
            "sequence": 0,
            "participants": ["Curia Caelestis"],
            "evidence": [{"source_item_id": "item-1", "snippet": "An omitted highlight"}],
        }],
        "relationships": [{
            "subject": "Curia Caelestis",
            "relation": "activates",
            "object": "Aether Engine",
            "evidence": [{"source_item_id": "item-1", "snippet": "Another non-source paraphrase"}],
        }],
        "delivery_assignments": [{
            "local_unit_id": "unit_0",
            "event_chain_ids": ["activation-chain"],
            "role": "primary_member",
            "confidence": 0.94,
            "reasoning": "The event unit directly narrates the activation.",
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
    assert result.delivery_assignments[0].source_item_ids == ["item-1"]
    assert result.delivery_assignments[0].event_chain_ids == ["activation-chain"]
    prompt = json.loads(handler.calls[0][0][1]["content"])
    assert prompt["local_text_units"][0]["item_keys"] == ["curia.activation:0"]
    system_prompt = " ".join(handler.calls[0][0][0]["content"].split())
    assert "never prove story-chain membership" in system_prompt


def test_missing_delivery_assignment_becomes_explicit_unassigned_without_repair():
    handler = FakeHandler([json.dumps({
        "terms": [], "entities": [], "facts": [], "events": [], "relationships": [],
    })])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()], scope=AnalysisScope.NARRATIVE_CONTEXT
    )

    assert len(handler.calls) == 1
    assert result.delivery_assignments[0].role == "unassigned"
    assert result.delivery_assignments[0].source_item_ids == ["item-1"]


def test_model_schema_does_not_expose_backend_owned_metadata():
    handler = StructuredFakeHandler(json.dumps({
        "terms": [], "entities": [], "facts": [], "events": [], "relationships": [],
    }))

    StructuredNeologismExtractor(handler).extract([source_item()])

    _, schema, schema_name, temperature = handler.calls[0]
    definitions = schema["$defs"]
    assert "provenance" not in definitions["SourceEvidence"]["properties"]
    assert "provenance" not in definitions["EntityContribution"]["properties"]
    assert "source_item_ids" not in definitions["DeliveryAssignment"]["properties"]
    for definition in ("FactContribution", "EventChainContribution", "RelationshipContribution"):
        assert "provenance" not in definitions[definition]["properties"]
        assert "tentative" not in definitions[definition]["properties"]
    assert schema_name == "remis_context_extraction"
    assert temperature == 0.0


def test_false_or_missing_fixed_metadata_is_normalized_without_repair():
    evidence = {"source_item_id": "source_0", "provenance": "user_confirmed"}
    handler = FakeHandler([json.dumps({
        "terms": [],
        "entities": [{
            "name": "Curia Caelestis",
            "entity_type": "organization/faction",
            "evidence": [evidence],
            "provenance": "script_derived",
        }],
        "facts": [{
            "subject": "Curia Caelestis",
            "predicate": "activates",
            "object": "Aether Engine",
            "evidence": [evidence],
            "tentative": False,
        }],
        "events": [{
            "chain_id": "activation-chain",
            "event": "Curia Caelestis activates the Aether Engine",
            "sequence": 0,
            "participants": ["Curia Caelestis"],
            "evidence": [evidence],
        }],
        "relationships": [{
            "subject": "Curia Caelestis",
            "relation": "activates",
            "object": "Aether Engine",
            "evidence": [evidence],
            "provenance": "user_confirmed",
            "tentative": False,
        }],
    })])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()], scope=AnalysisScope.NARRATIVE_CONTEXT
    )

    assert len(handler.calls) == 1
    assert result.entities[0].provenance == "text_inferred"
    assert result.facts[0].tentative is True
    assert result.events[0].tentative is True
    assert result.relationships[0].tentative is True
    assert result.entities[0].evidence[0].provenance == "text_inferred"


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


def test_model_input_keeps_original_key_while_evidence_uses_short_alias():
    handler = FakeHandler([json.dumps({
        "terms": [{
            "original": "Aether Engine",
            "category": "technology",
            "suggestion": "以太引擎",
            "reasoning": "事件标题和描述共同表明这是专名。",
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()],
        target_language="zh-CN",
        reasoning_language="zh-CN",
    )

    request = json.loads(handler.calls[0][0][1]["content"])
    supplied = request["source_items"][0]
    assert supplied["source_item_id"] == "source_0"
    assert supplied["item_key"] == "curia.activation:0"
    assert supplied["relative_path"] == "events/first.yml"
    assert supplied["source_order"] == 7
    assert supplied["source_text"] == source_item().source_text
    assert result.terms[0].evidence[0].source_item_id == "item-1"
    system_prompt = handler.calls[0][0][0]["content"]
    assert "author-provided structure" in system_prompt
    assert "zh-CN" in system_prompt


def test_invalid_contribution_is_dropped_without_repairing_the_batch():
    invalid = json.dumps({
        "terms": [{
            "original": "Hallucinated Term",
            "category": "other",
            "evidence": [{"source_item_id": "item-1", "snippet": "not in source"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid])

    result = StructuredNeologismExtractor(handler).extract([source_item()])

    assert result.terms == []
    assert len(handler.calls) == 1


def test_invalid_contribution_does_not_raise_after_one_bad_response():
    invalid = json.dumps({
        "terms": [{
            "original": "Hallucinated Term",
            "category": "other",
            "evidence": [{"source_item_id": "item-1", "snippet": "not in source"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid])

    assert StructuredNeologismExtractor(handler).extract([source_item()]).terms == []
    assert len(handler.calls) == 1


def test_evidence_snippet_normalizes_only_source_preserving_typography():
    item = source_item("Remis said, \u201cOpen the Meridian Gate\u2014now.\u201d")
    payload = json.dumps({
        "terms": [{
            "original": "Meridian Gate",
            "category": "place",
            "evidence": [{
                "source_item_id": "item-1",
                "snippet": 'remis said, "open the meridian gate-now."',
            }],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract([item])

    assert result.terms[0].evidence[0].snippet == (
        "Remis said, \u201cOpen the Meridian Gate\u2014now.\u201d"
    )


def test_evidence_highlight_can_align_paradox_formatting_tokens_to_source():
    item = source_item("Open the Meridian#r Gate#! now.")
    payload = json.dumps({
        "terms": [{
            "original": "Meridian Gate",
            "category": "place",
            "evidence": [{
                "source_item_id": "item-1",
                "snippet": "open the meridian gate now.",
            }],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract([item])

    assert result.terms[0].evidence[0].snippet == "Open the Meridian#r Gate#! now."


def test_terms_use_short_source_aliases_and_backend_restores_stable_identity():
    item = source_item()
    payload = json.dumps({
        "terms": [{
            "original": "Aether Engine",
            "category": "technology",
            "confidence": 0.9,
            "suggestion": "以太引擎",
            "reasoning": "A named technology; retain a consistent technical translation.",
            "evidence": [{"source_item_id": "source_0"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract(
        [item], target_language="Chinese", reasoning_language="English"
    )

    request = json.loads(handler.calls[0][0][1]["content"])
    prompt_item = request["source_items"][0]
    assert prompt_item["source_item_id"] == "source_0"
    assert prompt_item["item_key"] == "curia.activation:0"
    assert prompt_item["relative_path"] == "events/first.yml"
    assert prompt_item["source_order"] == 7
    assert prompt_item["source_text"] == item.source_text
    assert item.source_item_id not in handler.calls[0][0][1]["content"]
    term = result.terms[0]
    assert term.suggestion == "以太引擎"
    assert term.reasoning.startswith("A named technology")
    assert term.evidence[0].source_item_id == item.source_item_id
    assert term.evidence[0].item_key == item.item_key
    assert term.evidence[0].snippet == "Aether Engine"


def test_missing_or_hallucinated_highlight_never_becomes_grounding_evidence(caplog):
    hallucinated_highlight = "hallucinated detail " * 40
    payload = json.dumps({
        "terms": [{
            "original": "Aether Engine",
            "category": "technology",
            "evidence": [{
                "source_item_id": "source_0",
                "snippet": hallucinated_highlight,
            }],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract([source_item()])

    assert result.terms[0].evidence[0].snippet == "Aether Engine"
    assert "hallucinated detail" in caplog.text
    assert hallucinated_highlight not in caplog.text


def test_grounded_contribution_gets_deterministic_atomic_source_evidence():
    text = "Remis opened the Meridian Gate after the council vote."
    payload = json.dumps({
        "terms": [],
        "entities": [{
            "name": "Meridian Gate",
            "entity_type": "place",
            "description": "A gate opened after a vote.",
            "evidence": [{
                "source_item_id": "item-1",
                "snippet": "The gate was opened following the vote.",
            }],
            "provenance": "text_inferred",
        }],
        "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item(text)],
        scope=AnalysisScope.NARRATIVE_CONTEXT,
    )

    assert result.entities[0].evidence[0].snippet == "Meridian Gate"


def test_fact_without_snippet_still_requires_all_fact_anchors_in_source():
    payload = json.dumps({
        "terms": [],
        "entities": [],
        "facts": [{
            "subject": "Curia Caelestis",
            "predicate": "destroys",
            "object": "Aether Engine",
            "evidence": [{"source_item_id": "source_0"}],
            "provenance": "text_inferred",
            "tentative": True,
        }],
        "events": [], "relationships": [],
    })
    handler = FakeHandler([payload])

    result = StructuredNeologismExtractor(handler).extract(
        [source_item()], scope=AnalysisScope.NARRATIVE_CONTEXT
    )

    assert result.facts == []
    assert len(handler.calls) == 1


def test_unknown_source_item_drops_only_the_invalid_contribution():
    invalid = json.dumps({
        "terms": [{
            "original": "Curia Caelestis",
            "category": "faction",
            "evidence": [{"source_item_id": "other-item", "snippet": "Curia Caelestis"}],
        }],
        "entities": [], "facts": [], "events": [], "relationships": [],
    })
    handler = FakeHandler([invalid])

    assert StructuredNeologismExtractor(handler).extract([source_item()]).terms == []
    assert len(handler.calls) == 1


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


def test_invalid_json_does_not_get_a_second_repair_attempt():
    handler = FakeHandler([
        "not-json",
        "still-not-json",
        json.dumps({"terms": [], "entities": [], "facts": [], "events": [], "relationships": []}),
    ])

    with pytest.raises(NeologismMiningError, match=r"after one repair \(invalid_json\)"):
        StructuredNeologismExtractor(handler).extract([source_item()])

    assert len(handler.calls) == 2
    assert len(handler.responses) == 1


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
