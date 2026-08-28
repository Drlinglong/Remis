import json
import re
from pathlib import Path


FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "vic3_adj_multilingual_v1"
    / "cases.json"
)


def load_fixture():
    with FIXTURE_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def test_fixture_has_ten_aligned_cases_for_every_target_language():
    fixture = load_fixture()

    assert fixture["schema_version"] == 1
    assert fixture["fixture_id"] == "vic3-adj-multilingual-v1"
    assert fixture["source_language"] == "english"
    assert fixture["case_count"] == 10
    assert fixture["target_example_count"] == 100
    assert fixture["selection"] == {
        "adj_definition_count": 5,
        "adj_reference_count": 5,
        "policy": (
            "Same ten keys aligned across English and every official non-English "
            "localization shipped in this corpus snapshot."
        ),
    }

    target_languages = fixture["target_languages"]
    assert len(target_languages) == 10
    assert len(set(target_languages)) == 10

    cases = fixture["cases"]
    assert len({case["id"] for case in cases}) == 10
    assert len({case["key"] for case in cases}) == 10
    assert all(set(case["official_targets"]) == set(target_languages) for case in cases)


def test_fixture_records_auditable_source_provenance():
    fixture = load_fixture()
    sha256_pattern = re.compile(r"^[0-9a-f]{64}$")

    assert sha256_pattern.fullmatch(fixture["corpus_fingerprint_sha256"])
    for case in fixture["cases"]:
        entries = [case["source"], *case["official_targets"].values()]
        for entry in entries:
            assert entry["value"]
            assert entry["source_file"].endswith(".yml")
            assert entry["source_line"] > 0
            assert sha256_pattern.fullmatch(entry["source_file_sha256"])


def test_reference_cases_name_every_adj_token_present_in_the_english_source():
    fixture = load_fixture()

    for case in fixture["cases"]:
        if case["kind"] == "adj_definition":
            assert case["key"].endswith("_ADJ")
            assert case["referenced_adj_tokens"] == []
            continue

        assert case["kind"] == "adj_reference"
        assert case["referenced_adj_tokens"]
        for token in case["referenced_adj_tokens"]:
            assert f"${token}$" in case["source"]["value"]


def test_fixture_anchors_known_cross_language_morphology_contracts():
    fixture = load_fixture()
    cases = {case["id"]: case for case in fixture["cases"]}

    egyptian = cases["definition_egy_adj"]["official_targets"]
    assert egyptian["simp_chinese"]["value"] == "埃及"
    assert egyptian["japanese"]["value"] == "エジプト"
    assert egyptian["german"]["value"] == "Ägyptisch"
    assert egyptian["russian"]["value"] == "Египетск"

    connection = cases["reference_portuguese_connection"]["official_targets"]
    assert "$POR_ADJ$の" in connection["japanese"]["value"]
    assert "$POR_ADJ$" not in connection["french"]["value"]

    flagship = cases["reference_british_flagship"]["official_targets"]
    assert "$GBR_ADJ$ий" in flagship["russian"]["value"]

    uprising = cases["reference_bharat_uprising"]["official_targets"]
    assert "$BHT_ADJ$er" in uprising["german"]["value"]
