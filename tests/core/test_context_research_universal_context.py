from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_compiler import ContextResearchDraftCompiler
from scripts.core.services.context_research_contract import ContextAnalysisRequest
from scripts.core.services.context_research_external_context import (
    ContextResearchExternalContext,
    ExternalContextSource,
)
from scripts.core.services.context_research_universal_context import (
    build_universal_translation_context,
)


def _request() -> ContextAnalysisRequest:
    return ContextAnalysisRequest(
        project_id="universal-context",
        game_id="victoria3",
        description_language="zh-CN",
        source_items=(SourceItem(
            source_item_id="source-1",
            relative_path="events/demo.yml",
            item_key="demo.1.desc",
            source_order=0,
            source_text="Remis receives a warning.",
        ),),
        external_context=ContextResearchExternalContext(
            game_id="victoria3",
            metadata={"name": "Horizon Signal", "tags": ["Story"]},
            metadata_source=ExternalContextSource(
                kind="mod_metadata", locator=".metadata/metadata.json", status="loaded",
                sha256="a" * 64,
            ),
            workshop={"title": "Horizon Signal Workshop", "description": "A public story."},
            workshop_source=ExternalContextSource(
                kind="steam_workshop", locator="steam_workshop:1", status="loaded",
                sha256="b" * 64,
            ),
        ),
    )


def test_universal_context_is_short_and_records_external_provenance() -> None:
    context = build_universal_translation_context(_request(), (), (), ())

    assert 0 < len(context.text) <= 300
    assert "Horizon Signal" in context.text
    assert context.external_source_kinds == ("mod_metadata", "steam_workshop")
    assert context.generation == "deterministic_extract"


def test_compiler_publishes_universal_context_without_replacing_evidence_items() -> None:
    request = _request()
    findings = {
        "event_chains": [{
            "chain_id": "warning",
            "sequence": 0,
            "event": "Remis receives a warning.",
            "local_unit_ids": ["unit_0"],
            "source_item_ids": ["source-1"],
            "evidence": [{"source_item_ids": ["source-1"], "snippet": "warning"}],
        }],
    }

    draft = ContextResearchDraftCompiler().compile(findings, request)

    assert draft.universal_translation_context.text
    assert draft.universal_translation_context.source_item_ids == ("source-1",)
    assert draft.diagnostics["compiler"]["universal_translation_context"]["external_source_kinds"] == [
        "mod_metadata", "steam_workshop",
    ]
    assert draft.event_chains[0].event == "Remis receives a warning."
