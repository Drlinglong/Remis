from scripts.core.context_local_units import ContextLocalUnitBuilder
from scripts.core.neologism_extraction import SourceItem


def _item(key: str, order: int) -> SourceItem:
    return SourceItem(
        source_item_id=f"source-{order}",
        relative_path="localisation/english/events.yml",
        item_key=key,
        source_order=order,
        source_text=f"Text {order}",
    )


def test_numeric_event_anchor_keeps_cross_game_suffixes_in_one_local_unit():
    units = ContextLocalUnitBuilder.build([
        _item("distribution_of_power_laws.2.f", 0),
        _item("distribution_of_power_laws.2.a", 1),
        _item("distribution_of_power_laws.2.b", 2),
        _item("distribution_of_power_laws.3.t", 3),
    ])

    assert [[item.item_key for item in unit.items] for unit in units] == [
        [
            "distribution_of_power_laws.2.f",
            "distribution_of_power_laws.2.a",
            "distribution_of_power_laws.2.b",
        ],
        ["distribution_of_power_laws.3.t"],
    ]


def test_numbered_stellaris_options_group_without_merging_neighboring_events():
    units = ContextLocalUnitBuilder.build([
        _item("akx.9021.name", 0),
        _item("akx.9021.desc", 1),
        _item("akx.9021.a", 2),
        _item("akx.9101.name", 3),
        _item("akx.9101.a.notspiritual.tooltip", 4),
    ])

    assert [unit.unit_key.rsplit("::", 1)[-1] for unit in units] == [
        "akx.9021",
        "akx.9101",
    ]


def test_non_numbered_title_description_pairs_are_conservative_local_units():
    units = ContextLocalUnitBuilder.build([
        _item("WORM_CHAIN_1_title", 0),
        _item("WORM_CHAIN_1_desc", 1),
        _item("happy_with_open_loop_temple", 2),
        _item("happy_with_open_loop_temple_desc", 3),
    ])

    assert [len(unit.items) for unit in units] == [2, 2]


def test_numbered_event_membership_expands_to_title_description_and_options():
    units = ContextLocalUnitBuilder.build([
        _item("toxoids.7255.name", 0),
        _item("toxoids.7255.desc", 1),
        _item("toxoids.7255.a", 2),
        _item("toxoids.7255.b", 3),
    ])

    assert len(units) == 1
    assert units[0].unit_id == "unit_0"
    assert [item.item_key for item in units[0].items] == [
        "toxoids.7255.name",
        "toxoids.7255.desc",
        "toxoids.7255.a",
        "toxoids.7255.b",
    ]
