from __future__ import annotations

import pytest

from scripts.core.neologism_extraction import (
    AnalysisScope,
    SourceEvidence,
    SourceItem,
    StructuredNeologismExtraction,
    TermContribution,
)
from scripts.core.services.context_tree_v2_term_only import (
    DISCARDED_FIELDS,
    PROMPT_VERSION,
    ContextTreeV2TermOnlyService,
    TermOnlyContractError,
)


def _evidence(source_id: str) -> SourceEvidence:
    return SourceEvidence(
        source_item_id=source_id,
        relative_path="events/test.yml",
        item_key=f"test.{source_id}",
        source_order=int(source_id.rsplit("-", 1)[-1]),
    )


def _structured_term(
    original: str,
    suggestion: str,
    reasoning: str,
    source_id: str,
) -> TermContribution:
    return TermContribution(
        original=original,
        suggestion=suggestion,
        reasoning=reasoning,
        evidence=[_evidence(source_id)],
    )


def _source_item() -> SourceItem:
    return SourceItem(
        source_item_id="source-0",
        relative_path="events/test.yml",
        item_key="test.title",
        source_order=0,
        source_text="The Aether Engine starts.",
    )


def test_duplicate_terms_keep_every_batch_variant_and_use_original_normalized_key():
    batches = [
        StructuredNeologismExtraction(terms=[
            _structured_term("The Aether Engine", "以太引擎", "batch zero", "source-0"),
        ]),
        {
            "terms": [
                {
                    "original": "Aether Engine",
                    "translation": "以太发动机",
                    "explanation": "batch one first",
                    "evidence": ["source-1"],
                },
                {
                    "original": "AETHER ENGINE",
                    "suggestion": "以太核心",
                    "reasoning": "batch one second",
                    "evidence": ["source-2"],
                },
            ],
        },
    ]

    result = ContextTreeV2TermOnlyService().build(batches)

    term = result.term_for("aether engine")
    assert term.normalized_key == "aether engine"
    assert [variant.batch_index for variant in term.variants] == [0, 1, 1]
    assert [variant.translation for variant in term.variants] == [
        "以太引擎", "以太发动机", "以太核心",
    ]
    assert [variant.explanation for variant in term.variants] == [
        "batch zero", "batch one first", "batch one second",
    ]
    assert term.first_variant is term.variants[0]
    assert term.selected_variant is None
    assert {item.source_item_id for item in term.evidence} == {
        "source-0", "source-1", "source-2",
    }


def test_term_and_variant_order_is_stable_and_contains_batch_tiebreakers():
    batches = [
        {"terms": [
            {
                "original": "Zeta",
                "suggestion": "Z",
                "reasoning": "z",
                "evidence": ["source-0"],
            },
            {
                "original": "Alpha",
                "suggestion": "A0",
                "reasoning": "a0",
                "evidence": ["source-1"],
            },
        ]},
        {"terms": [{
            "original": "Alpha",
            "suggestion": "A1",
            "reasoning": "a1",
            "evidence": ["source-2"],
        }]},
    ]

    service = ContextTreeV2TermOnlyService()
    first = service.build(batches)
    second = service.build(batches)

    assert [term.normalized_key for term in first.terms] == ["alpha", "zeta"]
    assert [term.first_variant.variant_id for term in first.terms] == [
        "alpha::batch-0000::term-0001",
        "zeta::batch-0000::term-0000",
    ]
    assert [variant.variant_id for variant in first.term_for("alpha").variants] == [
        variant.variant_id for variant in second.term_for("alpha").variants
    ]
    assert first.term_for("alpha").first_variant.translation == "A0"


def test_approval_saves_selected_variant_and_removes_other_pending_variants():
    result = ContextTreeV2TermOnlyService().build([
        {"terms": [
            {
                "original": "Aether Engine",
                "suggestion": "first",
                "reasoning": "first reason",
                "evidence": ["source-0"],
            },
            {
                "original": "Aether Engine",
                "suggestion": "second",
                "reasoning": "second reason",
                "evidence": ["source-1"],
            },
        ]},
        {"terms": [{
            "original": "Other Term",
            "suggestion": "other",
            "reasoning": "other reason",
            "evidence": ["source-2"],
        }]},
    ])

    selected = result.approve_term("Aether Engine", "aether engine::batch-0000::term-0001")
    assert selected.translation == "second"
    term = result.term_for("Aether Engine")
    assert term.selected_variant_id == selected.variant_id
    assert term.selected_variant is selected
    assert term.pending_variants == ()
    assert [variant.translation for variant in term.variants] == ["second"]

    result.approve_all()
    assert result.term_for("Other Term").selected_variant.translation == "other"
    assert all(term.selected_variant_id for term in result.terms)
    assert all(not term.pending_variants for term in result.terms)


class _FakeSink:
    def __init__(self) -> None:
        self.payloads = []

    def persist(self, payload) -> None:
        self.payloads.append(payload)


def test_persistence_sink_receives_only_explicit_terms_only_contract():
    sink = _FakeSink()
    result = ContextTreeV2TermOnlyService().execute(
        [{
            "terms": [{
                "original": "Aether Engine",
                "translation": "以太引擎",
                "explanation": "one-pass suggestion",
                "evidence": ["source-0"],
            }],
            "local_fragments": [],
            "unit_routes": [],
            "entities": [],
            "facts": [],
            "relationships": [],
            "catalog": [],
            "entity_digest": [],
            "event_context": [],
        }],
        sink=sink,
    )

    assert result.prompt_version == PROMPT_VERSION == "context-archive-tree-v2"
    assert len(sink.payloads) == 1
    payload = sink.payloads[0]
    payload_dict = payload.as_dict()
    assert payload.analysis_scope == "terms_only"
    assert payload.prompt_version == PROMPT_VERSION
    assert set(payload.discarded_fields) == set(DISCARDED_FIELDS)
    assert set(payload.persisted_term_fields) == {
        "normalized_key", "original", "evidence", "variants", "selected_variant_id",
    }
    assert set(payload_dict) == {
        "schema_version", "analysis_scope", "prompt_version",
        "persisted_term_fields", "discarded_fields", "terms",
    }
    serialized_term = payload_dict["terms"][0]
    assert set(serialized_term) == {
        "normalized_key", "original", "evidence", "variants", "selected_variant_id",
    }
    assert not any(field in payload_dict for field in (
        "local_fragments", "unit_routes", "entities", "facts", "relationships",
        "catalog", "entity_digest", "event_context",
    ))


@pytest.mark.parametrize("narrative_field", ["entities", "local_fragments", "event_context"])
def test_narrative_payload_is_rejected_before_persistence(narrative_field):
    record = {
        "terms": [],
        narrative_field: [{"id": "narrative-output"}],
    }

    with pytest.raises(TermOnlyContractError, match=narrative_field):
        ContextTreeV2TermOnlyService().build([record])


def test_narrative_scope_is_rejected_even_without_non_empty_outputs():
    with pytest.raises(TermOnlyContractError, match="Narrative extraction"):
        ContextTreeV2TermOnlyService().build([{
            "analysis_scope": AnalysisScope.NARRATIVE_CONTEXT,
            "terms": [],
        }])


class _FakeStructuredExtractor:
    def __init__(self) -> None:
        self.calls = []

    def extract_chunks(self, chunks, *, scope, game_name, target_language, reasoning_language):
        self.calls.append({
            "chunks": chunks,
            "scope": scope,
            "game_name": game_name,
            "target_language": target_language,
            "reasoning_language": reasoning_language,
        })
        return [{
            "terms": [{
                "original": "Aether Engine",
                "suggestion": "fake-only",
                "reasoning": "no paid model",
                "evidence": ["source-0"],
            }],
        } for _ in chunks]


def test_execute_injects_fake_extractor_with_terms_only_and_records_skips():
    extractor = _FakeStructuredExtractor()
    result = ContextTreeV2TermOnlyService(extractor=extractor).execute(
        source_batches=[[_source_item()]],
        scope=AnalysisScope.TERMS_ONLY,
        target_language="zh-CN",
    )

    assert len(extractor.calls) == 1
    assert extractor.calls[0]["scope"] is AnalysisScope.TERMS_ONLY
    assert result.analysis_scope is AnalysisScope.TERMS_ONLY
    assert result.skipped == {
        "catalog": True,
        "entity_digest": True,
        "event_context": True,
    }
    assert result.term_for("Aether Engine").first_variant.translation == "fake-only"


class _FakeV2ExtractionService:
    def __init__(self) -> None:
        self.calls = []

    def extract(self, source_items, *, scope, target_language, prompt_version):
        self.calls.append({
            "source_items": source_items,
            "scope": scope,
            "target_language": target_language,
            "prompt_version": prompt_version,
        })
        return {
            "terms": [{
                "original": "Aether Engine",
                "suggestion": "handler-fake",
                "reasoning": "v2 extraction boundary",
                "evidence": [{"source_item_id": "source-0"}],
            }],
            "local_fragments": [],
            "unit_routes": [],
            "entities": [],
            "facts": [],
            "events": [],
            "relationships": [],
        }


def test_execute_accepts_fake_v2_extraction_service_without_real_model_invocation():
    handler = _FakeV2ExtractionService()
    result = ContextTreeV2TermOnlyService().run(
        source_batches=[[_source_item()]],
        extractor=handler,
    )

    assert len(handler.calls) == 1
    assert handler.calls[0]["scope"] is AnalysisScope.TERMS_ONLY
    assert handler.calls[0]["prompt_version"] == "context-archive-tree-v2"
    assert result.term_for("Aether Engine").first_variant.translation == "handler-fake"
