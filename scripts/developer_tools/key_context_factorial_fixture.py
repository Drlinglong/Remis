"""Fixture loading and adaptation for the key-context factorial benchmark."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from scripts.developer_tools.evaluate_translation_quality import (
    resolve_case,
    sha256_text,
)


LANGUAGE_FOLDER_TO_CODE = {
    "simp_chinese": "zh-CN",
    "japanese": "ja",
    "korean": "ko",
    "german": "de",
    "french": "fr",
    "spanish": "es",
    "braz_por": "pt-BR",
    "polish": "pl",
    "russian": "ru",
    "turkish": "tr",
}
DOLLAR_TOKEN_RE = re.compile(r"\$([^$]+)\$")


def parse_dollar_tokens(text: str) -> list[dict[str, Any]]:
    """Parse Paradox dollar tokens without treating modifiers as part of the key."""
    parsed = []
    for match in DOLLAR_TOKEN_RE.finditer(text or ""):
        parts = match.group(1).split("|")
        parsed.append(
            {
                "raw": match.group(0),
                "base_key": parts[0],
                "modifiers": parts[1:],
            }
        )
    return parsed


def compare_reference_tokens(source: str, target: str) -> dict[str, Any]:
    source_tokens = parse_dollar_tokens(source)
    target_tokens = parse_dollar_tokens(target)
    source_exact = Counter(
        (item["base_key"], tuple(item["modifiers"])) for item in source_tokens
    )
    target_exact = Counter(
        (item["base_key"], tuple(item["modifiers"])) for item in target_tokens
    )
    source_bases = Counter(item["base_key"] for item in source_tokens)
    target_bases = Counter(item["base_key"] for item in target_tokens)
    remaining_targets = [
        (item["base_key"], set(item["modifiers"])) for item in target_tokens
    ]
    source_modifiers_preserved = True
    for source_token in source_tokens:
        source_modifiers = set(source_token["modifiers"])
        match_index = next(
            (
                index
                for index, (base_key, modifiers) in enumerate(remaining_targets)
                if base_key == source_token["base_key"]
                and source_modifiers <= modifiers
            ),
            None,
        )
        if match_index is None:
            source_modifiers_preserved = False
            break
        remaining_targets.pop(match_index)
    missing_bases = list((source_bases - target_bases).elements())
    extra_bases = list((target_bases - source_bases).elements())
    substitutions = []
    remaining_extra = Counter(extra_bases)
    for base_key in missing_bases:
        candidate = base_key.removesuffix("_ADJ")
        if candidate != base_key and remaining_extra[candidate]:
            substitutions.append(
                {"source_base_key": base_key, "target_base_key": candidate}
            )
            remaining_extra[candidate] -= 1
    return {
        "source_tokens": source_tokens,
        "target_tokens": target_tokens,
        "exact_token_multiset_preserved": source_exact == target_exact,
        "base_key_multiset_preserved": source_bases == target_bases,
        "source_modifiers_preserved": source_modifiers_preserved,
        "missing_base_keys": missing_bases,
        "extra_base_keys": extra_bases,
        "token_substitutions": substitutions,
    }


def reference_structural_grade_ceiling(source: str, target: str) -> str:
    """Return the best rubric grade still possible before language review."""
    comparison = compare_reference_tokens(source, target)
    dynamic_bases = {
        token["base_key"]
        for token in comparison["source_tokens"]
        if token["base_key"] in {"FIRST_ADJ", "SECOND_ADJ"}
    }
    if dynamic_bases.intersection(comparison["missing_base_keys"]):
        return "FAIL"
    if (
        comparison["base_key_multiset_preserved"]
        and comparison["source_modifiers_preserved"]
    ):
        return "FULL"
    return "PARTIAL"


def classify_reference_strategy(source: str, target: str) -> str:
    comparison = compare_reference_tokens(source, target)
    source_adj = [
        token for token in comparison["source_tokens"]
        if token["base_key"].endswith("_ADJ")
    ]
    target_bases = Counter(
        token["base_key"] for token in comparison["target_tokens"]
    )
    if source_adj and all(target_bases[token["base_key"]] for token in source_adj):
        return "preserve_adj"
    stripped = [token["base_key"].removesuffix("_ADJ") for token in source_adj]
    if source_adj and all(target_bases[base] for base in stripped):
        return "substitute_base_tag"
    if source_adj and not any(
        target_bases[token["base_key"]] or target_bases[stripped_base]
        for token, stripped_base in zip(source_adj, stripped)
    ):
        return "hardcoded"
    return "mixed"


def read_factorial_fixture(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    fixture = json.loads(raw)
    if fixture.get("schema_version") != 1:
        raise ValueError(
            "Unsupported factorial fixture schema_version: "
            f"{fixture.get('schema_version')!r}"
        )
    is_native = isinstance(fixture.get("translation_cases"), list)
    is_official_adj = fixture.get("fixture_id") == "vic3-adj-multilingual-v1"
    is_composition = fixture.get("fixture_id") == "vic3-adj-composition-zh-cn-v1"
    if not is_native and not is_official_adj and not is_composition:
        raise ValueError(
            "Fixture must use the native factorial schema, vic3-adj-multilingual-v1, "
            "or vic3-adj-composition-zh-cn-v1"
        )
    if is_native and not isinstance(fixture.get("language_policies"), dict):
        raise ValueError("Native factorial fixture requires language_policies")
    fixture["_fixture_path"] = str(path.resolve())
    return fixture, sha256_text(raw)


def resolve_factorial_cases(
    fixture: dict[str, Any],
    policies: dict[str, str],
    case_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if fixture.get("fixture_id") == "vic3-adj-multilingual-v1":
        return _resolve_official_adj_cases(fixture, policies, case_ids)
    if fixture.get("fixture_id") == "vic3-adj-composition-zh-cn-v1":
        return _resolve_composition_cases(fixture, case_ids)

    raw_cases = fixture["translation_cases"]
    ids = [case.get("id") for case in raw_cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Factorial fixture contains duplicate case ids")

    selected = [case for case in raw_cases if not case_ids or case.get("id") in case_ids]
    missing = (case_ids or set()) - {case.get("id") for case in selected}
    if missing:
        raise ValueError(f"Unknown factorial case ids: {sorted(missing)}")

    resolved: list[dict[str, Any]] = []
    for raw_case in selected:
        case = resolve_case(raw_case)
        policy = raw_case.get("language_instruction") or fixture[
            "language_policies"
        ].get(case["target_lang"])
        if not isinstance(policy, str) or not policy.strip():
            raise ValueError(
                f"{case['id']} has no target-language policy for {case['target_lang']}"
            )
        case["language_instruction"] = policy.strip()
        _validate_case_contract(case)
        resolved.append(case)
    return resolved


def _composition_glossary_entries(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "entry_id": item["id"],
            "translations": {
                "en": item["source_value"],
                "zh-CN": item["target_value"],
            },
            "variants": {},
            "abbreviations": {},
            "raw_metadata": {
                "remarks": "Frozen lexical control shared by every experiment arm."
            },
        }
        for item in fixture["lexical_control"]["entries"]
    ]


def _resolve_composition_cases(
    fixture: dict[str, Any], case_ids: set[str] | None
) -> list[dict[str, Any]]:
    """Adapt paired definition/reference cases into two independently prompted tracks."""
    fixture_path = Path(fixture["_fixture_path"])
    definitions: dict[str, dict[str, Any]] = {}
    definition_case_ids: dict[str, list[str]] = defaultdict(list)
    for item in fixture["cases"]:
        key = item["definition"]["key"]
        existing = definitions.get(key)
        if existing and existing["gold"] != item["definition"]["gold"]:
            raise ValueError(f"Conflicting composition definition gold for {key}")
        definitions[key] = item["definition"]
        definition_case_ids[key].append(item["id"])

    tracks = (
        (
            "adj_definition",
            "vic3_adj_composition_zh_cn_definitions",
            list(definitions.values()),
        ),
        (
            "adj_reference",
            "vic3_adj_composition_zh_cn_references",
            [item["reference"] for item in fixture["cases"]],
        ),
    )
    resolved = []
    for track, case_id, items in tracks:
        if case_ids and case_id not in case_ids:
            continue
        source_entries = [
            {
                "key": item["key"],
                "text": item["source_value"],
                "line_number": item["provenance"].get("source_line", index),
            }
            for index, item in enumerate(items, start=1)
        ]
        expectations = (
            [
                {
                    "key": item["key"],
                    "category": "adj_definition",
                    "accepted_outputs": [item["gold"]],
                }
                for item in items
            ]
            if track == "adj_definition"
            else []
        )
        metadata = {}
        for item in items:
            if track == "adj_definition":
                related = definition_case_ids[item["key"]]
                metadata[item["key"]] = {
                    "kind": track,
                    "official_target": item["gold"],
                    "composition_case_ids": related,
                    "source_provenance": item["provenance"],
                    "referenced_adj_tokens": [],
                }
            else:
                composition = next(
                    case for case in fixture["cases"]
                    if case["reference"]["key"] == item["key"]
                )
                metadata[item["key"]] = {
                    "kind": track,
                    "official_target": item["gold"],
                    "composition_case_ids": [composition["id"]],
                    "source_provenance": item["provenance"],
                    "referenced_adj_tokens": [
                        variable["raw"] for variable in composition["variables"]
                    ],
                    "dynamic_variables": [],
                    "official_reference_strategy": "preserve_adj",
                }
        case = {
            "id": case_id,
            "track": track,
            "game_id": fixture["game_id"],
            "source_lang": "en",
            "target_lang": fixture["target_language"],
            "source_file": "vic3_adj_composition_zh_cn_v1/cases.json",
            "source_path": fixture_path,
            "keys": [item["key"] for item in items],
            "source_entries": source_entries,
            "focus": ["TAG_ADJ definition-reference composition"],
            "mod_context": (
                "Victoria 3 TAG_ADJ composition benchmark. Translate each entry "
                "independently while preserving output order."
            ),
            "language_instruction": fixture["prompt_policy"]["text"],
            "semantic_hints": {
                item["key"]: (
                    "semantic_type=country_adj_definition; "
                    "definition_role=reusable_country_entity; "
                    "contextual_morphology_owner=consuming_reference"
                    if track == "adj_definition"
                    else "semantic_type=country_adj_reference; "
                    "preserve_runtime_token=true; grammar_owner=use_site"
                )
                for item in items
            },
            "batch_semantic_hint": (
                "Translate country adjective definitions into reusable target-language "
                "country entity forms. Contextual grammar belongs to consuming "
                "references, not the definition. Return translated values only."
                if track == "adj_definition"
                else None
            ),
            "glossary_entries": _composition_glossary_entries(fixture),
            "expectations": expectations,
            "item_metadata": metadata,
            "composition_fixture_id": fixture["fixture_id"],
        }
        _validate_case_contract(case)
        resolved.append(case)

    if case_ids:
        missing = case_ids - {case["id"] for case in resolved}
        if missing:
            raise ValueError(f"Unknown factorial case ids: {sorted(missing)}")
    return resolved


def _resolve_official_adj_cases(
    fixture: dict[str, Any],
    policies: dict[str, str],
    case_ids: set[str] | None,
) -> list[dict[str, Any]]:
    fixture_path = Path(fixture["_fixture_path"])
    resolved = []
    for language_folder in fixture["target_languages"]:
        target_lang = LANGUAGE_FOLDER_TO_CODE.get(language_folder)
        if not target_lang:
            raise ValueError(f"Unsupported fixture target language: {language_folder}")
        if target_lang not in policies:
            raise ValueError(f"Missing language policy for {target_lang}")
        for kind, track_name in (
            ("adj_definition", "definitions"),
            ("adj_reference", "references"),
        ):
            case_id = f"vic3_adj_{language_folder}_{track_name}"
            if case_ids and case_id not in case_ids:
                continue
            items = [item for item in fixture["cases"] if item["kind"] == kind]
            source_entries = [
                {
                    "key": item["key"],
                    "text": item["source"]["value"],
                    "line_number": item["source"]["source_line"],
                }
                for item in items
            ]
            expectations = [
                {
                    "key": item["key"],
                    "category": item["kind"],
                    "accepted_outputs": [
                        item["official_targets"][language_folder]["value"]
                    ],
                }
                for item in items
                if kind == "adj_definition"
            ]
            item_metadata = {
                item["key"]: {
                    "fixture_case_id": item["id"],
                    "kind": item["kind"],
                    "focus": item["focus"],
                    "official_target": item["official_targets"][language_folder][
                        "value"
                    ],
                    "referenced_adj_tokens": item["referenced_adj_tokens"],
                    "dynamic_variables": [
                        token
                        for token in item["referenced_adj_tokens"]
                        if "FIRST_ADJ" in token or "SECOND_ADJ" in token
                    ],
                    "source_provenance": item["source"],
                    "target_provenance": item["official_targets"][language_folder],
                    "official_reference_strategy": classify_reference_strategy(
                        item["source"]["value"],
                        item["official_targets"][language_folder]["value"],
                    )
                    if kind == "adj_reference"
                    else None,
                }
                for item in items
            }
            case = {
                "id": case_id,
                "track": kind,
                "game_id": fixture["game_id"],
                "source_lang": "en",
                "target_lang": target_lang,
                "source_file": "vic3_adj_multilingual_v1/cases.json",
                "source_path": fixture_path,
                "keys": [item["key"] for item in items],
                "source_entries": source_entries,
                "focus": [f"official multilingual {track_name}"],
                "mod_context": (
                    "Official Victoria 3 localization morphology benchmark. "
                    f"This batch contains only {track_name}. Translate each entry "
                    "independently while preserving output order."
                ),
                "language_instruction": policies[target_lang],
                "semantic_hints": {
                    item["key"]: _official_semantic_hint(item, target_lang)
                    for item in items
                },
                "batch_semantic_hint": (
                    "type=country_adj_definition; "
                    f"lang={target_lang}; form=composable_country_definition"
                )
                if kind == "adj_definition"
                else None,
                "expectations": expectations,
                "item_metadata": item_metadata,
                "corpus_fingerprint_sha256": fixture["corpus_fingerprint_sha256"],
                "source_provenance": [
                    {
                        "key": item["key"],
                        "source_file": item["source"].get("source_file"),
                        "source_line": item["source"]["source_line"],
                        "source_file_sha256": item["source"].get(
                            "source_file_sha256"
                        ),
                    }
                    for item in items
                ],
            }
            _validate_case_contract(case)
            resolved.append(case)

    if case_ids:
        missing = case_ids - {case["id"] for case in resolved}
        if missing:
            raise ValueError(f"Unknown factorial case ids: {sorted(missing)}")
    return resolved


def _official_semantic_hint(item: dict[str, Any], target_lang: str) -> str:
    if item["kind"] == "adj_definition":
        return (
            "type=country_adj_definition; "
            f"lang={target_lang}; form=composable_country_definition"
        )
    tokens = ",".join(item["referenced_adj_tokens"])
    return (
        "type=reference; "
        f"lang={target_lang}; tokens={tokens}; form=contextual_grammar"
    )


def _validate_case_contract(case: dict[str, Any]) -> None:
    keys = [entry["key"] for entry in case["source_entries"]]
    base_keys = {_display_key(key) for key in keys}
    expectations = case.get("expectations", [])
    expectation_keys = [item.get("key") for item in expectations]
    if len(expectation_keys) != len(set(expectation_keys)):
        raise ValueError(f"{case['id']} contains duplicate expectation keys")
    unknown_expectations = {
        key for key in expectation_keys if key not in keys and key not in base_keys
    }
    if unknown_expectations:
        raise ValueError(
            f"{case['id']} expectations reference unknown keys: "
            f"{sorted(unknown_expectations)}"
        )

    semantic_hints = case.get("semantic_hints", {})
    if not isinstance(semantic_hints, dict):
        raise ValueError(f"{case['id']} semantic_hints must be an object")
    unknown_hints = {
        key for key in semantic_hints if key not in keys and key not in base_keys
    }
    if unknown_hints:
        raise ValueError(
            f"{case['id']} semantic_hints reference unknown keys: {sorted(unknown_hints)}"
        )


def _display_key(key: str) -> str:
    return key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key


def fixture_name(fixture: dict[str, Any]) -> str:
    return fixture.get("name") or fixture.get("fixture_id") or "key-context-factorial"
