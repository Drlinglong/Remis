import json

from scripts.developer_tools.key_context_semantic_routing import (
    COUNTRY_ADJ_DEFINITION_HINT,
    COUNTRY_ADJ_REFERENCE_HINT,
    attach_detected_semantic_hints,
    detect_country_adj_hint,
    load_official_country_tags,
    detect_language_specific_country_adj_hint,
)


def test_country_adj_detection_is_limited_to_official_tags():
    official = {"CHI", "GBR"}

    assert detect_country_adj_hint("CHI_ADJ:0", "Chinese", official) == (
        COUNTRY_ADJ_DEFINITION_HINT
    )
    assert detect_country_adj_hint("modland_ADJ:0", "Modlander", official) is None
    assert detect_country_adj_hint("XYZ_ADJ:0", "Modlander", official) is None
    assert detect_country_adj_hint("dynamic:0", "$CHI_ADJ$ power", official) == (
        COUNTRY_ADJ_REFERENCE_HINT
    )
    assert detect_country_adj_hint("dynamic:0", "$FIRST_ADJ$ power", official) is None


def test_catalog_validation_and_case_attachment(tmp_path):
    catalog_path = tmp_path / "tags.json"
    catalog_path.write_text(
        json.dumps({"schema_version": 1, "tag_count": 1, "tags": ["CHI"]}),
        encoding="utf-8",
    )
    tags = load_official_country_tags(catalog_path)
    [case] = attach_detected_semantic_hints(
        [
            {
                "source_entries": [
                    {"key": "CHI_ADJ:0", "text": "Chinese"},
                    {"key": "other:0", "text": "Popular Support"},
                ]
            }
        ],
        tags,
    )

    assert set(case["detected_semantic_hints"]) == {"CHI_ADJ:0"}


def test_h2_uses_target_language_runtime_forms_without_answer_leakage():
    official = {"POR", "GBR"}

    spanish_definition = detect_language_specific_country_adj_hint(
        "POR_ADJ:0", "Portuguese", "es", official
    )
    spanish_reference = detect_language_specific_country_adj_hint(
        "connection:0", "The $POR_ADJ$ Connection", "es", official
    )
    polish_definition = detect_language_specific_country_adj_hint(
        "GBR_ADJ:0", "British", "pl", official
    )

    assert "official_canonical_adjective_masculine_singular" in spanish_definition
    assert "compatible_masculine_singular_head" in spanish_reference
    assert "official_feminine_nominative_singular" in polish_definition
    assert "portugués" not in spanish_definition
    assert "Britannique" not in polish_definition
