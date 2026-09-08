from __future__ import annotations

from scripts.core.context_local_units import LocalTextUnit
from scripts.core.neologism_extraction import SourceItem
from scripts.core.services.context_research_entity_grading import (
    calculate_entity_frequency,
    grade_for_local_unit_coverage,
)


def _item(source_id: str, key: str, text: str) -> SourceItem:
    return SourceItem(
        source_item_id=source_id,
        relative_path="events/demo.yml",
        item_key=key,
        source_order=0,
        source_text=text,
    )


def test_frequency_grade_uses_distinct_units_not_raw_mentions():
    unit = LocalTextUnit(
        unit_id="unit_0",
        unit_key="events/demo.yml::demo.1",
        items=(
            _item("source-name", "demo.1.name", "Remis"),
            _item("source-desc", "demo.1.desc", "Remis meets Remis."),
        ),
    )

    result = calculate_entity_frequency("Remis", (), (unit,))

    assert result.mention_count == 3
    assert result.local_unit_ids == ("unit_0",)
    assert result.local_unit_coverage == 1
    assert result.source_files == ("events/demo.yml",)
    assert result.file_spread == 1
    assert result.frequency_grade == "C"


def test_frequency_grade_scans_merged_aliases_across_units():
    units = tuple(
        LocalTextUnit(
            unit_id=f"unit_{index}",
            unit_key=f"events/demo.yml::demo.{index}",
            items=(_item(f"source-{index}", f"demo.{index}.desc", text),),
        )
        for index, text in enumerate((
            "The Red Archivist arrives.",
            "Red Archivist speaks.",
            "The Archivist departs.",
        ))
    )

    result = calculate_entity_frequency(
        "The Red Archivist", ("The Archivist",), units,
    )

    assert result.mention_count == 3
    assert result.local_unit_ids == ("unit_0", "unit_1", "unit_2")
    assert result.file_spread == 1
    assert result.frequency_grade == "A"


def test_grade_thresholds_preserve_tree_v2_contract():
    assert grade_for_local_unit_coverage(0) == "C"
    assert grade_for_local_unit_coverage(1) == "C"
    assert grade_for_local_unit_coverage(2) == "B"
    assert grade_for_local_unit_coverage(3) == "A"
    assert grade_for_local_unit_coverage(9) == "A"
