from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_chunking_policy import ContextChunkingPolicy


def _item(key: str, order: int, text: str = "source text") -> SourceItem:
    return SourceItem(
        source_item_id=f"source-{order}",
        relative_path="localisation/english/events.yml",
        item_key=key,
        source_order=order,
        source_text=text,
    )


def test_unit_chunks_are_built_after_global_units_and_never_split_an_event():
    units = ContextLocalUnitBuilder.build([
        _item("toxoids.7255.name", 0),
        _item("toxoids.7255.a", 1),
        _item("toxoids.7255.b", 2),
        _item("toxoids.7260.name", 3),
        _item("toxoids.7260.desc", 4),
    ])

    chunks = ContextChunkingPolicy.unit_chunks(units, max_items=2, edge_units=1)

    assert [[unit.unit_id for unit in chunk.core_units] for chunk in chunks] == [
        ["unit_0"],
        ["unit_1"],
    ]
    assert [item.item_key for item in chunks[0].core_units[0].items] == [
        "toxoids.7255.name",
        "toxoids.7255.a",
        "toxoids.7255.b",
    ]
    assert [unit.unit_id for unit in chunks[0].edge_units] == ["unit_1"]
    assert [unit.unit_id for unit in chunks[1].edge_units] == ["unit_0"]


def test_edge_units_are_context_only_and_source_items_remain_ordered():
    units = ContextLocalUnitBuilder.build([
        _item("event.1.name", 0),
        _item("event.2.name", 1),
        _item("event.3.name", 2),
    ])

    chunks = ContextChunkingPolicy.unit_chunks(units, max_items=1, edge_units=1)

    assert [unit.unit_id for unit in chunks[1].core_units] == ["unit_1"]
    assert [unit.unit_id for unit in chunks[1].edge_units] == ["unit_0", "unit_2"]
    assert [item.source_order for item in chunks[1].source_items] == [0, 1, 2]
