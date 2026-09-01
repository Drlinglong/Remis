import pytest

from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_corpus_tools import (
    BoundCorpusTools,
    CorpusSourceItem,
    CorpusToolLimits,
    InMemoryCorpus,
    ReadOnlyRemisCorpusTools,
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
