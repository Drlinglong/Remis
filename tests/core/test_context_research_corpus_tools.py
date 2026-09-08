import json

import pytest

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_corpus_tools import (
    BoundCorpusTools,
    CorpusSourceItem,
    CorpusToolLimits,
    InMemoryCorpus,
    OwnedShardCorpusView,
    ReadOnlyRemisCorpusTools,
    ShardLease,
)


def _tools(**kwargs):
    corpus = InMemoryCorpus([
        CorpusSourceItem(
            source_item_id="source-1",
            path="archive/events.yml",
            key="event_meridian_gate",
            text="The Cartographers map the Meridian Gate event.",
        ),
        CorpusSourceItem(
            source_item_id="source-2",
            path="archive/lore.yml",
            key="lore_accord",
            text="The Accord of Echoes preserves an older route.",
        ),
    ])
    return ReadOnlyRemisCorpusTools(corpus, CorpusToolLimits(**kwargs))


def test_search_is_bounded_and_keeps_stable_evidence_identity():
    result = _tools(max_items=1).search_source_items("project-a", "cartographers")

    assert result["count"] == 1
    assert result["items"][0]["source_item_id"] == "source-1"
    assert result["read_only"] is True


def test_request_scoped_view_cannot_escape_project_or_source_snapshot():
    bound = BoundCorpusTools(_tools(), "project-a", ["source-2"])

    result = bound.read_source_items(["source-1", "source-2"])

    assert [item["source_item_id"] for item in result["items"]] == ["source-2"]
    assert result["rejected_source_item_ids"] == ["source-1"]
    assert bound.search_source_items("event") ["items"] == []


def test_request_scoped_view_rejects_an_empty_snapshot():
    with pytest.raises(ValueError, match="non-empty source snapshot"):
        BoundCorpusTools(_tools(), "project-a", [])


def test_total_output_budget_is_hard_even_for_long_source_text():
    tools = ReadOnlyRemisCorpusTools(
        InMemoryCorpus([CorpusSourceItem("source-1", "x" * 1000)]),
        CorpusToolLimits(max_items=4, max_item_chars=4000, max_total_chars=30),
    )

    result = tools.read_source_items("project-a", ["source-1"])
    record = result["items"][0]

    assert sum(len(str(value)) for value in record.values()) <= 30


def test_list_paginates_with_a_bound_offset_and_reports_more_records():
    tools = _tools(max_items=1)

    first = tools.list_source_items("project-a", offset=0)
    second = tools.list_source_items("project-a", offset=first["next_offset"])

    assert first["has_more"] is True
    assert first["next_offset"] == 1
    assert second["items"][0]["source_item_id"] == "source-2"
    assert second["has_more"] is False
    with pytest.raises(ValueError):
        tools.list_source_items("project-a", offset=-1)


def test_read_distinguishes_missing_items_from_output_truncation():
    result = _tools(max_items=1).read_source_items(
        "project-a", ["source-1", "source-2", "missing"],
    )

    assert result["missing_source_item_ids"] == ["missing"]
    assert result["truncated_source_item_ids"] == ["source-2"]


def test_metadata_is_bounded_and_sensitive_keys_are_removed_recursively():
    tools = ReadOnlyRemisCorpusTools(InMemoryCorpus([CorpusSourceItem(
        "source-1",
        "safe text",
        metadata={
            "author": "Linglong",
            "api_key": "must-not-leak",
            "nested": {"Authorization": "Bearer secret", "genre": "fantasy"},
        },
    )]))

    metadata = tools.read_source_items("project-a", ["source-1"])["items"][0]["metadata"]

    assert metadata == {"author": "Linglong", "nested": {"genre": "fantasy"}}


def test_bound_units_keep_stellaris_event_options_with_their_event_family():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml",
            item_key=key,
            source_order=index,
            source_text=text,
        )
        for index, (key, text) in enumerate((
            ("remis_crisis.1.t", "Dawn of a New Order"),
            ("remis_crisis.1.desc", "Remis reorganizes the Republic."),
            ("remis_crisis.1.c", "We will never kneel! Declare War."),
            ("remis_crisis.2.desc_text", "Opponents disappear."),
        ))
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    units = bound.list_local_units()["units"]

    assert [unit["derived_unit_key"] for unit in units] == [
        "remis_crisis.1", "remis_crisis.2",
    ]
    assert units[0]["item_keys"] == [
        "remis_crisis.1.t", "remis_crisis.1.desc", "remis_crisis.1.c",
    ]
    assert bound.read_local_units(["unit_0"])["units"][0]["entries"][2]["text"].startswith(
        "We will never kneel"
    )


def test_bound_unit_search_returns_the_complete_matching_family():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml",
            item_key=key,
            source_order=index,
            source_text=text,
        )
        for index, (key, text) in enumerate((
            ("remis_crisis.1.desc", "Remis reorganizes the Republic."),
            ("remis_crisis.1.c", "Declare War."),
        ))
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    result = bound.search_local_units("declare war")

    assert result["count"] == 1
    assert result["units"][0]["item_keys"] == [
        "remis_crisis.1.desc", "remis_crisis.1.c",
    ]


def test_manifest_exposes_bounded_size_for_adaptive_overlap_planning():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml" if index < 2 else "lore/remis.yml",
            item_key=f"remis_crisis.{index}.desc",
            source_order=index,
            source_text=f"Source {index}",
        )
        for index in range(3)
    )
    corpus_items = tuple(
        CorpusSourceItem(
            item.source_item_id,
            item.source_text,
            path=item.relative_path,
            key=item.item_key or "",
        )
        for item in source_items
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus(corpus_items)),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    manifest = bound.corpus_manifest()

    assert manifest["source_item_count"] == 3
    assert manifest["local_unit_count"] == 3
    assert manifest["paths"][0] == {
        "path": "events/remis.yml", "source_item_count": 2,
    }
    assert manifest["recommended_planning_mode"] == "single_shard_per_role"
    assert "Overlap is investigative only" in manifest["overlap_policy"]


def test_path_scoped_lists_are_paginated_without_hiding_boundary_context():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/a.yml" if index < 3 else "events/b.yml",
            item_key=f"event.{index}.desc",
            source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(4)
    )
    corpus_items = tuple(
        CorpusSourceItem(
            item.source_item_id, item.source_text,
            path=item.relative_path, key=item.item_key or "",
        )
        for item in source_items
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus(corpus_items), CorpusToolLimits(max_items=2)),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    first = bound.list_source_items(path="events/a.yml")
    second = bound.list_source_items(path="events/a.yml", offset=first["next_offset"])
    units = bound.list_local_units(path="events/b.yml")

    assert [item["source_item_id"] for item in first["items"]] == ["source-0", "source-1"]
    assert [item["source_item_id"] for item in second["items"]] == ["source-2"]
    assert units["units"][0]["paths"] == ["events/b.yml"]
    assert all(unit["derived_unit_key"] == "event.3" for unit in units["units"])


def test_investigation_shards_are_contiguous_and_overlap_only_at_unit_boundaries():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml",
            item_key=f"event.{index}.desc",
            source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(20)
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    shard_page = bound.investigation_shards()
    shards = shard_page["shards"]

    assert [shard["core_local_unit_ids"] for shard in shards] == [
        [f"unit_{index}" for index in range(12)],
        [f"unit_{index}" for index in range(12, 20)],
    ]
    assert shards[0]["overlap_local_unit_ids"] == []
    assert shards[1]["overlap_local_unit_ids"] == ["unit_11"]
    assert all(shard["within_core_read_budget"] for shard in shards)
    assert all(shard["read_budget"]["max_requests"] == 6 for shard in shards)
    assert all(shard["read_budget"]["max_tool_calls"] == 12 for shard in shards)
    assert shard_page["has_more"] is False


def test_investigation_shards_never_split_a_key_family_and_manifest_exposes_them():
    source_items = []
    for index in range(9):
        source_items.extend((
            SourceItem(
                source_item_id=f"source-{index}-title",
                relative_path="events/remis.yml",
                item_key=f"event.{index}.t",
                source_order=len(source_items),
                source_text=f"Title {index}",
            ),
            SourceItem(
                source_item_id=f"source-{index}-desc",
                relative_path="events/remis.yml",
                item_key=f"event.{index}.desc",
                source_order=len(source_items) + 1,
                source_text=f"Description {index}",
            ),
        ))
    source_items = tuple(source_items)
    corpus_items = tuple(
        CorpusSourceItem(
            item.source_item_id, item.source_text,
            path=item.relative_path, key=item.item_key or "",
        )
        for item in source_items
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus(corpus_items)),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    shard_page = bound.investigation_shards()
    shards = shard_page["shards"]
    manifest = bound.corpus_manifest()
    core_ids = [unit_id for shard in shards for unit_id in shard["core_local_unit_ids"]]

    assert len(core_ids) == 9
    assert len(set(core_ids)) == 9
    assert all(
        shard["core_source_item_count"] <= 20
        and shard["core_source_item_count"] % 2 == 0
        for shard in shards
    )
    assert manifest["shards"] == shards
    filtered = bound.investigation_shards(path="events/remis.yml")
    assert filtered["shards"] == shards


def test_investigation_shards_page_is_bounded_and_can_be_advanced():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml",
            item_key=f"event.{index}.desc",
            source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(30)
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([]), CorpusToolLimits(max_items=2)),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )

    first = bound.investigation_shards()
    second = bound.investigation_shards(offset=first["next_offset"])

    assert first["count"] <= 2
    assert first["has_more"] is True
    manifest = bound.corpus_manifest()
    assert manifest["shard_count"] == first["total_count"]
    assert len(json.dumps(manifest, ensure_ascii=False)) <= 8000
    assert second["offset"] == first["next_offset"]
    assert {item["shard_id"] for item in first["shards"]}.isdisjoint(
        item["shard_id"] for item in second["shards"]
    )


def test_read_investigation_shards_returns_complete_units_and_rejects_bad_requests():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}",
            relative_path="events/remis.yml",
            item_key=f"event.{index}.desc",
            source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(20)
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])),
        "project-a",
        [item.source_item_id for item in source_items],
        source_items=source_items,
    )
    shards = bound.investigation_shards()["shards"]
    result = bound.read_investigation_shards([item["shard_id"] for item in shards])

    assert result["count"] == len(shards)
    assert result["shards"][0]["core_local_unit_ids"] == shards[0]["core_local_unit_ids"]
    assert result["shards"][0]["units"][0]["local_unit_id"] == "unit_0"
    assert result["shards"][1]["overlap_local_unit_ids"] == ["unit_11"]
    with pytest.raises(ValueError, match="at most 3"):
        bound.read_investigation_shards([f"investigation-{index:03d}" for index in range(4)])
    with pytest.raises(ValueError, match="unknown"):
        bound.read_investigation_shards(["unknown-shard"])

    assert bound.validate_delegation_task(
        "Inspect investigation-000 and investigation-001."
    ) == ("investigation-000", "investigation-001")
    with pytest.raises(ValueError, match="must name 1-3"):
        bound.validate_delegation_task("Inspect every unit in the corpus.")
    with pytest.raises(ValueError, match="at most 3"):
        bound.validate_delegation_task(
            "Inspect investigation-000 investigation-001 investigation-002 "
            "investigation-003."
        )


def test_id_only_snapshot_is_normalized_into_local_units_and_shards():
    reader = InMemoryCorpus([
        {"source_item_id": "source-1", "relative_path": "events/demo.yml",
         "item_key": "demo.1.desc", "source_text": "Description"},
        {"source_item_id": "source-2", "relative_path": "events/demo.yml",
         "item_key": "demo.1.c", "source_text": "Choice"},
    ])
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(reader), "project-a", ["source-1", "source-2"],
    )

    manifest = bound.corpus_manifest()

    assert manifest["source_item_count"] == 2
    assert manifest["local_unit_count"] == 1
    assert manifest["shard_count"] == 1
    assert bound.list_local_units()["units"][0]["item_keys"] == [
        "demo.1.desc", "demo.1.c",
    ]


def test_owned_shard_view_rejects_out_of_lease_units_and_marks_overlap_context():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}", relative_path="events/demo.yml",
            item_key=f"event.{index}.desc", source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(20)
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])), "project-a",
        [item.source_item_id for item in source_items], source_items=source_items,
    )
    view = OwnedShardCorpusView(bound, bound.shard_lease("investigation-001"))

    overlap = view.read_local_units(["unit_11"])["units"][0]
    owner = view.read_local_units(["unit_12"])["units"][0]

    assert overlap["evidence_role"] == "context_only"
    assert overlap["entries"][0]["evidence_role"] == "context_only"
    assert owner["evidence_role"] == "owner"
    source_result = view.read_source_items(["source-11", "source-12"])
    assert [item["evidence_role"] for item in source_result["items"]] == [
        "context_only", "owner",
    ]
    external = view.search_source_items("Event 0")["items"]
    assert external[0]["ownership"] == "external_context_only"
    with pytest.raises(ValueError, match="only leased shard"):
        view.read_investigation_shards(["investigation-002"])


def test_multi_shard_lease_allows_exact_delegation_packet_and_keeps_core_owners():
    source_items = tuple(
        SourceItem(
            source_item_id=f"source-{index}", relative_path="events/demo.yml",
            item_key=f"event.{index}.desc", source_order=index,
            source_text=f"Event {index}",
        )
        for index in range(24)
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([])), "project-a",
        [item.source_item_id for item in source_items], source_items=source_items,
    )

    view = bound.owned_shard_view(("investigation-000", "investigation-001"))

    assert view.lease.shard_ids == ("investigation-000", "investigation-001")
    assert view.lease.role_for_unit("unit_11") == "owned"
    assert view.lease.ownership["unit_0"]["owner_shard_id"] == "investigation-000"
    assert view.lease.ownership["unit_12"]["owner_shard_id"] == "investigation-001"
    result = view.read_investigation_shards(
        ["investigation-000", "investigation-001"],
    )
    assert result["count"] == 2
    with pytest.raises(ValueError, match="only leased shards"):
        view.read_investigation_shards(["investigation-002"])


def test_large_unit_read_is_explicitly_truncated():
    item = SourceItem(
        source_item_id="source-1", relative_path="events/demo.yml",
        item_key="demo.1.desc", source_order=0, source_text="x" * 2_000,
    )
    bound = BoundCorpusTools(
        ReadOnlyRemisCorpusTools(InMemoryCorpus([]), CorpusToolLimits(max_item_chars=100, max_total_chars=150)),
        "project-a", ["source-1"], source_items=(item,),
    )

    result = bound.read_local_units(["unit_0"])

    unit = result["units"][0]
    assert unit["truncated"] is True
    assert unit["omitted_source_item_ids"] == ["source-1"]
