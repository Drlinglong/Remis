"""Focused tests for the Context Research short-ID boundary."""

from scripts.core.services.context_research_corpus_tools import (
    BoundCorpusTools,
    CorpusSourceItem,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
)
from scripts.core.services.context_research_ids import ShortIdRegistry
from scripts.core.services.context_research_shard_memo import ShardMemoCollector


def _bound():
    items = [
        CorpusSourceItem(
            f"source-item-{index:064x}", f"Event {index}",
            path="events/demo.yml", key=f"event.{index}.desc",
        )
        for index in range(20)
    ]
    return BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus(items)),
        "project-a", [item.source_item_id for item in items],
    )


def test_registry_is_one_based_and_rejects_unknown_without_fuzzy_matching():
    registry = ShortIdRegistry.from_snapshot(
        ["hash-a", "hash-b"], ["unit_0", "unit_1"],
    )

    assert registry.source_alias("hash-a") == "S001"
    assert registry.unit_alias("unit_1") == "U002"
    assert registry.resolve("source", "S001")[0] == "hash-a"
    assert registry.resolve("unit", "s001")[1].code == "unknown_id"
    assert registry.resolve("source", "S2")[0] == "hash-b"
    assert registry.resolve("source", "S999")[1].suggestion is None


def test_model_tools_use_short_ids_and_restore_canonical_input():
    bound = _bound()

    listed = bound.list_source_items(_model_facing=True)
    assert [item["source_item_id"] for item in listed["items"]][:3] == [
        "S001", "S002", "S003",
    ]
    units = bound.read_local_units(["U001"], _model_facing=True)
    assert units["units"][0]["local_unit_id"] == "U001"
    assert units["units"][0]["entries"][0]["source_item_id"] == "S001"
    assert bound.read_source_items(["S002"])["items"][0]["source_item_id"] == (
        "source-item-" + f"{1:064x}"
    )


def test_owned_view_reads_external_context_but_marks_claim_status():
    bound = _bound()
    view = bound.owned_shard_view("investigation-000")

    result = view.read_local_units(["U014", "U999"], _model_facing=True)

    assert result["units"][0]["ownership"] == "external_context_only"
    assert result["id_rejections"][0]["code"] == "unknown_id"
    source_result = view.read_source_items(["S014"], _model_facing=True)
    assert source_result["items"][0]["ownership"] == "external_context_only"


def test_memo_aliases_restore_and_external_claims_are_removed():
    registry = ShortIdRegistry.from_snapshot(
        ["source-0", "source-1"], ["unit_0", "unit_1"],
    )
    collector = ShardMemoCollector(({
        "shard_id": "investigation-000",
        "core_local_unit_ids": ["unit_0"],
        "overlap_local_unit_ids": [],
    },), id_registry=registry)
    collector.add({
        "role": "event_investigator",
        "shard_ids": ["investigation-000"],
        "core_local_unit_ids": ["U001"],
        "units": [{
            "local_unit_id": "U001", "ownership": "core", "disposition": "modeled",
            "content_role": "event_narrative",
            "delivery_route": "event",
            "evidence": ["S001", "S002"],
            "entity_mentions": [{
                "entity_id": "person-a", "name": "Person A", "entity_type": "person",
                "summary": "Person A participates in the event.",
                "evidence": [{"source_item_ids": ["S001"]}],
            }],
            "findings": {
                "event_chains": [{
                    "chain_id": "chain-a", "sequence": 0, "event": "Event",
                    "local_unit_ids": ["U001", "U002"],
                    "evidence": [{"source_item_ids": ["S002"]}],
                }],
                "reference_assets": [{
                    "asset_id": "asset-a", "name": "Asset", "local_unit_id": "U002",
                    "evidence": [{"source_item_ids": ["S002"]}],
                }],
            },
        }],
    })

    result = collector.collect()
    event = result.findings.event_chains[0]
    assert event.local_unit_ids == ("unit_0",)
    assert result.findings.reference_assets[0].local_unit_id is None
    assert result.findings.event_chains[0].evidence[0].source_item_ids == ("source-1",)
    assert result.findings.entities[0].evidence[0].source_item_ids == ("source-0",)
    assert result.units[0].evidence == ("source-0", "source-1")
    assert any(item["code"] == "claim_outside_lease" for item in result.findings.diagnostics["id_rejections"])
