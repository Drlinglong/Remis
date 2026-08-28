import json
from collections import Counter, defaultdict
from pathlib import Path


FIXTURE_DIR = Path(__file__).parents[1] / "fixtures/vic3_adj_multilingual_v1"


def test_luna_reference_annotations_are_complete_and_internally_consistent():
    rubric = json.loads(
        (FIXTURE_DIR / "reference_rubric_luna_v1.json").read_text(
            encoding="utf-8"
        )
    )
    items = rubric["items"]
    counts = Counter(item["grade"] for item in items)

    assert rubric["annotation_count"] == len(items) == 50
    assert counts == Counter({"FULL": 42, "PARTIAL": 8})
    assert rubric["summary"] == {
        "FULL": 42,
        "PARTIAL": 8,
        "FAIL": 0,
        "total": 50,
    }

    by_language = defaultdict(Counter)
    for item in items:
        by_language[item["target_language"]][item["grade"]] += 1
        assert set(item["dynamic_variables"]) <= {"FIRST_ADJ", "SECOND_ADJ"}
        assert set(item["dynamic_variables"]) <= set(item["runtime_variables"])
    for language, expected in rubric["language_summary"].items():
        assert by_language[language] == Counter(
            {grade: count for grade, count in expected.items() if count}
        )


def test_official_non_preserving_strategies_are_never_full():
    rubric = json.loads(
        (FIXTURE_DIR / "reference_rubric_luna_v1.json").read_text(
            encoding="utf-8"
        )
    )

    for item in rubric["items"]:
        if item["variable_strategy"] in {
            "preserved",
            "preserved_with_modifier",
            "preserved_with_suffix",
        }:
            assert item["grade"] == "FULL"
        else:
            assert item["grade"] == "PARTIAL"
