"""Score paired TAG_ADJ definitions and consuming references after expansion."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from scripts.developer_tools.key_context_factorial_fixture import (
    compare_reference_tokens,
    parse_dollar_tokens,
)


def render_reference(reference: str, substitutions: dict[str, str]) -> str:
    """Expand protected dollar tokens while treating modifiers as token metadata."""
    rendered = reference
    for token in parse_dollar_tokens(reference):
        replacement = substitutions.get(token["base_key"])
        if replacement is None:
            continue
        rendered = rendered.replace(token["raw"], replacement, 1)
    return rendered


def score_composition_pair(
    specification: dict[str, Any],
    definition_output: str,
    reference_output: str,
) -> dict[str, Any]:
    definition = specification["definition"]
    reference = specification["reference"]
    token_score = compare_reference_tokens(reference["source_value"], reference_output)
    substitutions = {definition["key"]: definition_output}
    rendered_output = render_reference(reference_output, substitutions)
    definition_exact = definition_output.strip() == definition["gold"].strip()
    reference_exact = reference_output.strip() == reference["gold"].strip()
    rendered_exact = rendered_output.strip() == specification["rendered"][
        "expected"
    ].strip()
    token_contract = (
        token_score["base_key_multiset_preserved"]
        and token_score["source_modifiers_preserved"]
    )
    return {
        "case_id": specification["id"],
        "synthetic": specification["synthetic"],
        "requires_linker": specification["grammar_expectation"]["requires_linker"],
        "definition_key": definition["key"],
        "reference_key": reference["key"],
        "definition_output": definition_output,
        "reference_output": reference_output,
        "rendered_output": rendered_output,
        "definition_exact": definition_exact,
        "reference_exact": reference_exact,
        "rendered_exact": rendered_exact,
        "token_contract_passed": token_contract,
        "token_semantics": token_score,
        "structural_composition_passed": definition_exact and token_contract,
        "exact_rendered_match": rendered_exact,
        "exact_rendered_match_is_diagnostic_only": True,
    }


def _score_mixed_composition_results(
    fixture: dict[str, Any],
    resolved_cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    cases_by_id = {case["id"]: case for case in resolved_cases}
    cells = []
    for result in results:
        case = cases_by_id[result["id"]]
        outputs_by_key = {
            entry["key"].rsplit(":", 1)[0]: output
            for entry, output in zip(
                case["source_entries"], result.get("outputs") or []
            )
        }
        pair_scores = [
            score_composition_pair(
                specification,
                outputs_by_key.get(specification["definition"]["key"], ""),
                outputs_by_key.get(specification["reference"]["key"], ""),
            )
            for specification in fixture["composition_pairs"]
        ]
        cells.append(
            {
                "arm_id": result["arm_id"],
                "repetition": result["repetition"],
                "execution_failure": bool(result.get("execution_failure")),
                "pair_count": len(pair_scores),
                "structural_composition_pass_count": sum(
                    score["structural_composition_passed"] for score in pair_scores
                ),
                "exact_rendered_match_count": sum(
                    score["exact_rendered_match"] for score in pair_scores
                ),
                "pairs": pair_scores,
            }
        )
    return {
        "fixture_id": fixture["fixture_id"],
        "measurement": (
            "Production-like mixed-batch composition. Exact rendered gold is "
            "diagnostic; alternate natural Chinese remains eligible for review."
        ),
        "cells": sorted(
            cells, key=lambda item: (item["arm_id"], item["repetition"])
        ),
    }


def score_composition_results(
    fixture: dict[str, Any],
    resolved_cases: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if fixture.get("fixture_id") == "vic3-adj-production-mixed-zh-cn-v1":
        return _score_mixed_composition_results(fixture, resolved_cases, results)

    if fixture.get("fixture_id") != "vic3-adj-composition-zh-cn-v1":
        return None
    cases_by_id = {case["id"]: case for case in resolved_cases}
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[(result["arm_id"], result["repetition"])].append(result)

    cells = []
    for (arm_id, repetition), arm_results in sorted(grouped.items()):
        outputs_by_track: dict[str, dict[str, str]] = {}
        execution_failures = []
        for result in arm_results:
            case = cases_by_id[result["id"]]
            execution_failures.append(result.get("execution_failure"))
            outputs_by_track[case["track"]] = {
                entry["key"]: output
                for entry, output in zip(
                    case["source_entries"], result.get("outputs") or []
                )
            }
        definition_outputs = outputs_by_track.get("adj_definition", {})
        reference_outputs = outputs_by_track.get("adj_reference", {})
        pair_scores = [
            score_composition_pair(
                specification,
                definition_outputs.get(specification["definition"]["key"], ""),
                reference_outputs.get(specification["reference"]["key"], ""),
            )
            for specification in fixture["cases"]
        ]
        cells.append(
            {
                "arm_id": arm_id,
                "repetition": repetition,
                "execution_failure": any(execution_failures),
                "pair_count": len(pair_scores),
                "structural_composition_pass_count": sum(
                    score["structural_composition_passed"] for score in pair_scores
                ),
                "exact_rendered_match_count": sum(
                    score["exact_rendered_match"] for score in pair_scores
                ),
                "linker_required_exact_match_count": sum(
                    score["exact_rendered_match"]
                    for score in pair_scores
                    if score["requires_linker"]
                ),
                "direct_compound_exact_match_count": sum(
                    score["exact_rendered_match"]
                    for score in pair_scores
                    if not score["requires_linker"]
                ),
                "pairs": pair_scores,
            }
        )
    return {
        "fixture_id": fixture["fixture_id"],
        "measurement": (
            "Definition exactness and protected-token preservation form the hard "
            "structural score. Exact rendered gold is diagnostic only; semantic "
            "completeness and fluency require blind language-quality review."
        ),
        "cells": cells,
    }
