"""Production semantic context for Victoria 3 country adjective slots."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from scripts.app_settings import CONFIG_DIR


logger = logging.getLogger(__name__)

COUNTRY_ADJ_DEFINITION_RE = re.compile(r"^([A-Z0-9]{3})_ADJ$")
COUNTRY_ADJ_REFERENCE_RE = re.compile(
    r"\$(?P<tag>[A-Z0-9]{3})_ADJ(?:\|[^$]+)?\$"
)
COUNTRY_TAG_CATALOG_PATH = (
    Path(CONFIG_DIR) / "key_context" / "vic3_official_country_tags_v1.json"
)
LANGUAGE_POLICY_PATH = (
    Path(CONFIG_DIR) / "key_context" / "vic3_language_policies_v1.json"
)

DEFINITION_FORMS = {
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

REFERENCE_FORMS = {
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

@lru_cache(maxsize=1)
def load_official_country_tags() -> frozenset[str]:
    """Load the versioned official Victoria 3 country-tag allowlist."""

    payload = json.loads(COUNTRY_TAG_CATALOG_PATH.read_text(encoding="utf-8"))
    tags = payload.get("tags")
    if payload.get("schema_version") != 1 or not isinstance(tags, list):
        raise ValueError("Invalid Victoria 3 country-tag catalog")
    normalized = frozenset(tag for tag in tags if isinstance(tag, str))
    if len(normalized) != payload.get("tag_count"):
        raise ValueError("Victoria 3 country-tag catalog count mismatch")
    return normalized


@lru_cache(maxsize=1)
def load_language_policies() -> dict[str, str]:
    """Load and validate the versioned H2 target-language policies."""

    payload = json.loads(LANGUAGE_POLICY_PATH.read_text(encoding="utf-8"))
    policies = payload.get("language_policies")
    if payload.get("schema_version") != 1 or not isinstance(policies, dict):
        raise ValueError("Invalid Victoria 3 language-policy resource")
    if set(policies) != set(DEFINITION_FORMS) or not all(
        isinstance(value, str) and value.strip() for value in policies.values()
    ):
        raise ValueError("Victoria 3 language policies are incomplete")
    return policies


def _display_key(key_info: Any) -> str:
    if not isinstance(key_info, dict):
        return ""
    entry = key_info.get("entry")
    base_key = getattr(entry, "base_key", None)
    if isinstance(base_key, str):
        return base_key
    key = str(key_info.get("key_part") or "")
    return key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key


def detect_hint(key: str, source_value: str, target_lang: str) -> str | None:
    """Return H2 metadata for one supported official definition or reference."""

    definition_form = DEFINITION_FORMS.get(target_lang)
    reference_form = REFERENCE_FORMS.get(target_lang)
    if not definition_form or not reference_form:
        return None

    official_tags = load_official_country_tags()
    match = COUNTRY_ADJ_DEFINITION_RE.fullmatch(key)
    if match and match.group(1) in official_tags:
        return (
            "semantic_type=country_adjective_definition; "
            f"required_runtime_form={definition_form}; "
            "contextual_morphology_owner=use_site; "
            "preserve_official_casing_and_spelling=true"
        )

    referenced_tags = {
        match.group("tag")
        for match in COUNTRY_ADJ_REFERENCE_RE.finditer(source_value)
    }
    if referenced_tags.intersection(official_tags):
        return (
            "semantic_type=country_adjective_reference; "
            "preserve_runtime_token=true; "
            f"runtime_form_contract={reference_form}; "
            "rewrite_surrounding_syntax_for_runtime_compatibility=true"
        )
    return None


def build_file_hints(
    *,
    game_id: str,
    target_lang: str,
    texts: Iterable[str],
    key_infos: Iterable[Any],
) -> list[str | None]:
    """Build index-aligned semantic hints without exposing raw keys to a model."""

    texts = list(texts)
    key_infos = list(key_infos)
    if game_id != "victoria3":
        return [None] * len(texts)
    if len(texts) != len(key_infos):
        raise ValueError("Victoria 3 semantic context is not aligned with source texts")
    try:
        if target_lang not in load_language_policies():
            return [None] * len(texts)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Victoria 3 semantic context is unavailable: %s", exc)
        return [None] * len(texts)
    try:
        return [
            detect_hint(_display_key(key_info), text, target_lang)
            for text, key_info in zip(texts, key_infos)
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Victoria 3 country-tag routing is unavailable: %s", exc)
        return [None] * len(texts)


def prompt_policy(target_lang: str, hints: Iterable[str | None]) -> str:
    """Return the single target-language policy only for a routed H2 batch."""

    if not any(hints):
        return ""
    try:
        return load_language_policies().get(target_lang, "")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Victoria 3 language policy is unavailable: %s", exc)
        return ""


def is_country_adj_reference(source_value: str) -> bool:
    """Identify official runtime references for conservative human review."""

    try:
        official_tags = load_official_country_tags()
        return any(
            match.group("tag") in official_tags
            for match in COUNTRY_ADJ_REFERENCE_RE.finditer(source_value)
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Victoria 3 reference review routing is unavailable: %s", exc)
        return False
