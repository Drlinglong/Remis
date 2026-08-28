import json
from pathlib import Path

from scripts.developer_tools.key_context_composition_score import (
    render_reference,
    score_composition_pair,
    score_composition_results,
)
from scripts.developer_tools.evaluate_key_context_factorial import OFFICIAL_LANGUAGE_POLICIES
from scripts.developer_tools.key_context_factorial_fixture import (
    read_factorial_fixture,
    resolve_factorial_cases,
)


FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "vic3_adj_composition_zh_cn_v1"
    / "cases.json"
)


def load_fixture_and_cases():
    fixture, _ = read_factorial_fixture(FIXTURE_PATH)
    return fixture, resolve_factorial_cases(fixture, OFFICIAL_LANGUAGE_POLICIES)


def test_companion_adapter_builds_separate_definition_and_reference_tracks():
    fixture, cases = load_fixture_and_cases()
    by_track = {case["track"]: case for case in cases}

    assert fixture["fixture_id"] == "vic3-adj-composition-zh-cn-v1"
    assert [entry["key"] for entry in by_track["adj_definition"]["source_entries"]] == [
        "POR_ADJ",
        "BHT_ADJ",
        "HUN_ADJ",
    ]
    assert len(by_track["adj_reference"]["source_entries"]) == 4
    assert by_track["adj_definition"]["glossary_entries"] == (
        by_track["adj_reference"]["glossary_entries"]
    )


def test_renderer_removes_token_modifiers_from_visible_expansion():
    assert render_reference("$BHT_ADJ|l$起义", {"BHT_ADJ": "印度"}) == "印度起义"


def test_pair_score_requires_definition_reference_and_rendered_collaboration():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    hun = next(case for case in fixture["cases"] if case["id"] == "synthetic_hun_adj_power")

    passing = score_composition_pair(hun, "匈牙利", "$HUN_ADJ$的实力")
    missing_linker = score_composition_pair(hun, "匈牙利", "$HUN_ADJ$实力")
    morphology_in_definition = score_composition_pair(hun, "匈牙利的", "$HUN_ADJ$实力")

    assert passing["structural_composition_passed"] is True
    assert passing["exact_rendered_match"] is True
    assert missing_linker["token_contract_passed"] is True
    assert missing_linker["rendered_output"] == "匈牙利实力"
    assert missing_linker["structural_composition_passed"] is True
    assert missing_linker["exact_rendered_match"] is False
    assert morphology_in_definition["rendered_output"] == "匈牙利的实力"
    assert morphology_in_definition["rendered_exact"] is True
    assert morphology_in_definition["definition_exact"] is False
    assert morphology_in_definition["structural_composition_passed"] is False


def test_cross_track_results_are_scored_per_arm_and_repetition():
    fixture, cases = load_fixture_and_cases()
    definitions = next(case for case in cases if case["track"] == "adj_definition")
    references = next(case for case in cases if case["track"] == "adj_reference")
    results = [
        {
            "id": definitions["id"],
            "arm_id": "B",
            "repetition": 1,
            "execution_failure": None,
            "outputs": ["葡萄牙", "印度", "匈牙利"],
        },
        {
            "id": references["id"],
            "arm_id": "B",
            "repetition": 1,
            "execution_failure": None,
            "outputs": [
                "$POR_ADJ$的关系",
                "$BHT_ADJ$起义",
                "$HUN_ADJ$的实力",
                "$BHT_ADJ|l$起义",
            ],
        },
    ]

    score = score_composition_results(fixture, cases, results)
    [cell] = score["cells"]
    assert cell["pair_count"] == 4
    assert cell["structural_composition_pass_count"] == 4
    assert cell["exact_rendered_match_count"] == 4
    assert cell["linker_required_exact_match_count"] == 2
    assert cell["direct_compound_exact_match_count"] == 2


def test_mixed_production_fixture_has_no_definition_track_hint():
    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "key_context_production_mixed_zh_cn_v1.json"
    )
    fixture, _ = read_factorial_fixture(fixture_path)
    cases = resolve_factorial_cases(fixture, fixture["language_policies"])

    assert len(cases) == 1
    assert "definition" not in cases[0]["mod_context"].lower()
    assert cases[0]["track"] == "mixed_production"
    assert [entry["key"] for entry in cases[0]["source_entries"]][:3] == [
        "CHI_ADJ:0",
        "mixed_popular_support:0",
        "mixed_chinese_culture:0",
    ]


def test_mixed_production_composition_scores_same_batch_outputs():
    fixture_path = (
        Path(__file__).parents[1]
        / "fixtures"
        / "key_context_production_mixed_zh_cn_v1.json"
    )
    fixture, _ = read_factorial_fixture(fixture_path)
    cases = resolve_factorial_cases(fixture, fixture["language_policies"])
    result = {
        "id": cases[0]["id"],
        "arm_id": "B",
        "repetition": 1,
        "execution_failure": None,
        "outputs": [
            "中国",
            "大众支持",
            "$CHI_ADJ$文化",
            "新秩序",
            "$CHI_ADJ$的实力",
            "中国代表团昨天抵达。",
            "$CHI_ADJ$人",
            "中文是所选语言。",
        ],
    }

    score = score_composition_results(fixture, cases, [result])

    assert score is not None
    assert score["cells"][0]["structural_composition_pass_count"] == 3
    assert score["cells"][0]["exact_rendered_match_count"] == 3
