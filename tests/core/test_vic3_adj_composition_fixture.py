import json
import re
from pathlib import Path


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "vic3_adj_composition_zh_cn_v1"
    / "cases.json"
)
TOKEN_RE = re.compile(r"\$([^$]+)\$")


def load_fixture():
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    return json.loads(raw), raw


def parse_tokens(value):
    tokens = []
    for match in TOKEN_RE.finditer(value):
        parts = match.group(1).split("|")
        tokens.append(
            {
                "raw": match.group(0),
                "base_key": parts[0],
                "modifiers": parts[1:],
            }
        )
    return tokens


def render_reference(case):
    rendered = case["reference"]["gold"]
    for token in parse_tokens(rendered):
        replacement = case["rendered"]["substitutions"][token["base_key"]]
        rendered = rendered.replace(token["raw"], replacement, 1)
    return rendered


def test_companion_fixture_is_utf8_reparseable_and_ids_are_unique():
    fixture, raw = load_fixture()

    assert "\ufffd" not in raw
    assert fixture["schema_version"] == 1
    assert fixture["fixture_id"] == "vic3-adj-composition-zh-cn-v1"
    assert fixture["target_language"] == "zh-CN"
    assert fixture == json.loads(raw.encode("utf-8").decode("utf-8"))

    case_ids = [case["id"] for case in fixture["cases"]]
    lexical_ids = [entry["id"] for entry in fixture["lexical_control"]["entries"]]
    assert len(case_ids) == len(set(case_ids))
    assert len(lexical_ids) == len(set(lexical_ids))
    assert not set(case_ids) & set(lexical_ids)


def test_policy_is_abstract_and_lexical_control_is_shared_by_all_arms():
    fixture, _ = load_fixture()
    policy = fixture["prompt_policy"]
    assert policy["scope"] == "shared_by_all_arms"
    assert "TAG_ADJ" in policy["text"]
    assert "Portuguese" not in policy["text"]
    assert "Hungarian" not in policy["text"]
    assert "power" not in policy["text"]
    assert "Connection" not in policy["text"]
    assert "Uprising" not in policy["text"]
    assert fixture["lexical_control"]["scope"] == "shared_by_all_arms"
    assert [
        (entry["source_value"], entry["target_value"])
        for entry in fixture["lexical_control"]["entries"]
    ] == [("American", "美利坚"), ("British", "不列颠")]


def test_each_pair_preserves_variables_modifiers_and_renders_from_definition_gold():
    fixture, _ = load_fixture()

    for case in fixture["cases"]:
        definition = case["definition"]
        reference = case["reference"]
        tokens = parse_tokens(reference["gold"])
        assert [item["raw"] for item in case["variables"]] == [
            token["raw"] for token in tokens
        ]
        assert [item["base_key"] for item in case["variables"]] == [
            token["base_key"] for token in tokens
        ]
        assert [item["modifiers"] for item in case["variables"]] == [
            token["modifiers"] for token in tokens
        ]
        assert case["modifiers"] == [
            modifier
            for variable in case["variables"]
            for modifier in variable["modifiers"]
        ]
        assert case["rendered"]["substitutions"] == {
            definition["key"]: definition["gold"]
        }
        assert render_reference(case) == case["rendered"]["expected"]
        assert definition["gold"]
        assert definition["gold"] not in {"匈牙利的", "印度的", "葡萄牙的"}


def test_fixture_contains_a_linker_required_and_direct_compound_contrast():
    fixture, _ = load_fixture()
    requiring = [
        case for case in fixture["cases"]
        if case["grammar_expectation"]["requires_linker"]
    ]
    direct = [
        case for case in fixture["cases"]
        if not case["grammar_expectation"]["requires_linker"]
    ]

    assert {case["id"] for case in requiring} == {
        "official_por_adj_connection",
        "synthetic_hun_adj_power",
    }
    assert {case["id"] for case in direct} == {
        "official_bht_adj_uprising",
        "synthetic_bht_adj_modifier_control",
    }
    assert {case["synthetic"] for case in requiring} == {False, True}
    assert {case["synthetic"] for case in direct} == {False, True}


def test_official_and_synthetic_provenance_boundaries_are_explicit():
    fixture, _ = load_fixture()

    for case in fixture["cases"]:
        definition_kind = case["definition"]["provenance"]["kind"]
        reference_kind = case["reference"]["provenance"]["kind"]
        assert definition_kind == "official_victoria3_snapshot"
        assert case["definition"]["provenance"]["source_fixture"] == (
            "vic3-adj-multilingual-v1"
        )
        if case["synthetic"]:
            assert reference_kind.startswith("synthetic_")
        else:
            assert reference_kind == "official_victoria3_snapshot"
            assert case["reference"]["provenance"]["source_fixture"] == (
                "vic3-adj-multilingual-v1"
            )
