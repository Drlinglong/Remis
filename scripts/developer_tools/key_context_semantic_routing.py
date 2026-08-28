"""Deterministic semantic routing used by the key-context benchmark."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scripts.developer_tools.key_context_factorial_fixture import parse_dollar_tokens


COUNTRY_ADJ_DEFINITION_RE = re.compile(r"^([A-Z0-9]{3})_ADJ$")

COUNTRY_ADJ_DEFINITION_HINT = (
    "semantic_type=country_adjective_definition; "
    "required_form=reusable_country_entity_stem; "
    "contextual_morphology_owner=use_site"
)
COUNTRY_ADJ_REFERENCE_HINT = (
    "semantic_type=country_adjective_reference; preserve_runtime_token=true; "
    "choose_use_site_morphology_from_the_current_sentence"
)

LANGUAGE_SPECIFIC_DEFINITION_FORMS = {
    "zh-CN": "official_reusable_country_entity_form_without_use_site_morphology",
    "ja": "official_reusable_country_entity_form_without_particles",
    "ko": "official_reusable_country_entity_form_without_particles",
    "de": "official_composable_adjective_base_without_inflectional_ending",
    "fr": "official_canonical_adjective_masculine_singular",
    "es": "official_canonical_adjective_masculine_singular",
    "pt-BR": "official_canonical_adjective_masculine_singular",
    "pl": "official_feminine_nominative_singular_localization_slot",
    "ru": "official_composable_adjective_stem_without_inflectional_ending",
    "tr": "official_country_related_slot_opaque_lexeme",
}

LANGUAGE_SPECIFIC_REFERENCE_FORMS = {
    "zh-CN": "runtime_value_is_country_entity_form; add_use_site_words_or_particles_outside_token",
    "ja": "runtime_value_is_country_entity_form; choose_japanese_word_order_and_particles_outside_token",
    "ko": "runtime_value_is_country_entity_form; choose_korean_word_order_and_particles_without_guessing_final_sound",
    "de": "runtime_value_is_adjective_base; add_contextual_inflectional_ending_outside_token",
    "fr": "runtime_value_is_opaque_masculine_singular_adjective; rewrite_with_compatible_masculine_singular_head",
    "es": "runtime_value_is_opaque_masculine_singular_adjective; rewrite_with_compatible_masculine_singular_head_and_postpose_adjective",
    "pt-BR": "runtime_value_is_opaque_masculine_singular_adjective; rewrite_with_compatible_masculine_singular_head_and_natural_word_order",
    "pl": "runtime_value_is_opaque_feminine_nominative_singular_slot; rewrite_around_a_compatible_feminine_nominative_head",
    "ru": "runtime_value_is_adjective_stem; add_independently_selected_gender_number_case_ending_outside_each_token",
    "tr": "runtime_value_is_opaque_country_related_lexeme; put_case_possessive_and_number_suffixes_on_the_head_noun_when_possible",
}


def load_official_country_tags(path: Path) -> set[str]:
    catalog = json.loads(path.read_text(encoding="utf-8"))
    tags = catalog.get("tags")
    if catalog.get("schema_version") != 1 or not isinstance(tags, list):
        raise ValueError(f"Invalid Victoria 3 country TAG catalog: {path}")
    normalized = {tag for tag in tags if isinstance(tag, str)}
    if len(normalized) != catalog.get("tag_count"):
        raise ValueError(f"Victoria 3 country TAG catalog count mismatch: {path}")
    return normalized


def detect_country_adj_hint(
    key: str, source_value: str, official_country_tags: set[str]
) -> str | None:
    display_key = key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key
    definition_match = COUNTRY_ADJ_DEFINITION_RE.fullmatch(display_key)
    if definition_match and definition_match.group(1) in official_country_tags:
        return COUNTRY_ADJ_DEFINITION_HINT

    referenced_tags = {
        token["base_key"].removesuffix("_ADJ")
        for token in parse_dollar_tokens(source_value)
        if token["base_key"].endswith("_ADJ")
    }
    if referenced_tags.intersection(official_country_tags):
        return COUNTRY_ADJ_REFERENCE_HINT
    return None


def attach_detected_semantic_hints(
    cases: list[dict[str, Any]], official_country_tags: set[str]
) -> list[dict[str, Any]]:
    routed = []
    for case in cases:
        detected = {}
        for entry in case["source_entries"]:
            hint = detect_country_adj_hint(
                entry["key"], entry["text"], official_country_tags
            )
            if hint:
                detected[entry["key"]] = hint
        routed.append({**case, "detected_semantic_hints": detected})
    return routed


def detect_language_specific_country_adj_hint(
    key: str,
    source_value: str,
    target_lang: str,
    official_country_tags: set[str],
) -> str | None:
    definition_form = LANGUAGE_SPECIFIC_DEFINITION_FORMS.get(target_lang)
    reference_form = LANGUAGE_SPECIFIC_REFERENCE_FORMS.get(target_lang)
    if not definition_form or not reference_form:
        raise ValueError(f"No H2 country adjective contract for {target_lang}")

    display_key = key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key
    definition_match = COUNTRY_ADJ_DEFINITION_RE.fullmatch(display_key)
    if definition_match and definition_match.group(1) in official_country_tags:
        return (
            "semantic_type=country_adjective_definition; "
            f"required_runtime_form={definition_form}; "
            "contextual_morphology_owner=use_site; preserve_official_casing_and_spelling=true"
        )

    referenced_tags = {
        token["base_key"].removesuffix("_ADJ")
        for token in parse_dollar_tokens(source_value)
        if token["base_key"].endswith("_ADJ")
    }
    if referenced_tags.intersection(official_country_tags):
        return (
            "semantic_type=country_adjective_reference; preserve_runtime_token=true; "
            f"runtime_form_contract={reference_form}; "
            "rewrite_surrounding_syntax_for_runtime_compatibility=true"
        )
    return None


def attach_language_specific_semantic_hints(
    cases: list[dict[str, Any]], official_country_tags: set[str]
) -> list[dict[str, Any]]:
    routed = []
    for case in cases:
        detected = {}
        for entry in case["source_entries"]:
            hint = detect_language_specific_country_adj_hint(
                entry["key"],
                entry["text"],
                case["target_lang"],
                official_country_tags,
            )
            if hint:
                detected[entry["key"]] = hint
        routed.append({**case, "language_specific_semantic_hints": detected})
    return routed
