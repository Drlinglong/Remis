"""Run a controlled key-context prompt experiment through the Remis prompt path."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.app_settings import MAX_RETRIES, PROJECT_ROOT
from scripts.core.api_handler import get_handler
from scripts.core.glossary_manager import glossary_manager
from scripts.utils.post_process_validator import PostProcessValidator
from scripts.utils.text_clean import mask_special_tokens
from scripts.utils.rate_limiter import rate_limiter
from scripts.developer_tools.evaluate_translation_quality import (
    build_translation_prompt,
    call_and_parse,
    discover_single_model,
    make_task,
    score_outputs,
    sha256_text,
    slugify,
)
from scripts.developer_tools.key_context_factorial_fixture import (
    compare_reference_tokens,
    fixture_name,
    read_factorial_fixture,
    reference_structural_grade_ceiling,
    resolve_factorial_cases,
)
from scripts.developer_tools.key_context_cost_estimate import (
    estimate_luna_batch_cost,
)
from scripts.developer_tools.key_context_composition_score import (
    score_composition_results,
)
from scripts.developer_tools.key_context_openrouter_batch import (
    build_openrouter_batch_manifest,
)
from scripts.developer_tools.key_context_openrouter_evidence import (
    OpenRouterAttemptError,
    call_openrouter_chat_with_evidence,
)
from scripts.developer_tools.key_context_lexical_control import (
    attach_lexical_control,
    load_lexical_control,
)
from scripts.developer_tools.key_context_semantic_routing import (
    attach_detected_semantic_hints,
    attach_language_specific_semantic_hints,
    load_official_country_tags,
)


DEFAULT_FIXTURE = (
    Path(PROJECT_ROOT)
    / "tests"
    / "fixtures"
    / "vic3_adj_multilingual_v1"
    / "cases.json"
)
DEFAULT_OUTPUT_DIR = Path(PROJECT_ROOT) / "benchmark_results" / "key_context_factorial"
DEFAULT_POLICY_FILE = (
    Path(PROJECT_ROOT) / "tests" / "fixtures" / "key_context_language_policies_v1.json"
)
DEFAULT_OFFICIAL_COUNTRY_TAGS = (
    Path(PROJECT_ROOT)
    / "tests"
    / "fixtures"
    / "vic3_official_country_tags_v1.json"
)

OFFICIAL_LANGUAGE_POLICIES = json.loads(DEFAULT_POLICY_FILE.read_text(encoding="utf-8"))[
    "language_policies"
]


@dataclass(frozen=True)
class ExperimentArm:
    arm_id: str
    label: str
    include_raw_key: bool = False
    include_language_policy: bool = False
    include_semantic_hint: bool = False
    include_detected_semantic_hint: bool = False
    include_language_specific_semantic_hint: bool = False
    exploratory: bool = False


ARMS = {
    "A": ExperimentArm("A", "production baseline"),
    "B": ExperimentArm("B", "target-language policy only", include_language_policy=True),
    "C": ExperimentArm("C", "raw key only", include_raw_key=True),
    "D": ExperimentArm(
        "D",
        "raw key plus target-language policy",
        include_raw_key=True,
        include_language_policy=True,
    ),
    "E": ExperimentArm(
        "E",
        "semantic hint only",
        include_semantic_hint=True,
        exploratory=True,
    ),
    "F": ExperimentArm(
        "F",
        "deterministic official-country semantic routing",
        include_detected_semantic_hint=True,
        exploratory=True,
    ),
    "G": ExperimentArm(
        "G",
        "raw key plus target-language policy with entry isolation",
        include_raw_key=True,
        include_language_policy=True,
        exploratory=True,
    ),
    "H": ExperimentArm(
        "H",
        "deterministic official-country semantic routing plus target-language policy",
        include_language_policy=True,
        include_detected_semantic_hint=True,
        exploratory=True,
    ),
    "H2": ExperimentArm(
        "H2",
        "language-specific official-country semantic routing plus target-language policy",
        include_language_policy=True,
        include_language_specific_semantic_hint=True,
        exploratory=True,
    ),
}
CORE_ARM_IDS = ("A", "B", "C", "D")


def _display_key(key: str) -> str:
    return key.rsplit(":", 1)[0] if key.rsplit(":", 1)[-1].isdigit() else key


def _lookup_by_key(mapping: dict[str, Any], key: str) -> Any:
    return mapping.get(key, mapping.get(_display_key(key)))


def _numbered_input(case: dict[str, Any], arm: ExperimentArm) -> str:
    lines = []
    hints = case.get("semantic_hints", {})
    for index, entry in enumerate(case["source_entries"], start=1):
        masked = mask_special_tokens(entry["text"])
        if arm.include_raw_key:
            lines.append(
                f'{index}. Localization key: "{_display_key(entry["key"])}"; '
                f'Source value: "{masked}"'
            )
            continue
        if arm.include_detected_semantic_hint:
            hint = _lookup_by_key(case.get("detected_semantic_hints", {}), entry["key"])
            if isinstance(hint, str) and hint.strip():
                lines.append(
                    f'{index}. Semantic hint: "{hint.strip()}"; '
                    f'Source value: "{masked}"'
                )
            else:
                lines.append(f'{index}. Source value: "{masked}"')
            continue
        if arm.include_language_specific_semantic_hint:
            hint = _lookup_by_key(
                case.get("language_specific_semantic_hints", {}), entry["key"]
            )
            if isinstance(hint, str) and hint.strip():
                lines.append(
                    f'{index}. Semantic hint: "{hint.strip()}"; '
                    f'Source value: "{masked}"'
                )
            else:
                lines.append(f'{index}. Source value: "{masked}"')
            continue
        if arm.include_semantic_hint and not case.get("batch_semantic_hint"):
            hint = _lookup_by_key(hints, entry["key"])
            if not isinstance(hint, str) or not hint.strip():
                raise ValueError(
                    f"{case['id']} arm {arm.arm_id} requires a semantic hint "
                    f"for {entry['key']}"
                )
            lines.append(
                f'{index}. Semantic hint: "{hint.strip()}"; '
                f'Source value: "{masked}"'
            )
            continue
        lines.append(f'{index}. "{masked}"')
    return "\n".join(lines)


def build_arm_prompt(
    case: dict[str, Any], handler: Any, task: Any, arm: ExperimentArm
) -> str:
    """Start from the production prompt and apply one isolated arm manipulation."""
    prompt = build_translation_prompt(case, handler, task)
    baseline_arm = ARMS["A"]
    baseline_input = _numbered_input(case, baseline_arm)
    if prompt.count(baseline_input) != 1:
        raise ValueError(
            f"{case['id']} production prompt did not contain one exact input block"
        )

    arm_input = _numbered_input(case, arm)
    replacement = arm_input
    if arm.include_semantic_hint and case.get("batch_semantic_hint"):
        replacement = (
            "SEMANTIC CONTRACT (EXPERIMENTAL):\n"
            f"{case['batch_semantic_hint']}\n\n"
            + arm_input
        )
    if arm.include_language_policy:
        replacement = (
            "TARGET-LANGUAGE MORPHOLOGY POLICY (EXPERIMENTAL):\n"
            f"{case['language_instruction']}\n"
            "Apply this policy only when its stated conditions match the input. "
            "Do not change the required value-only JSON output contract.\n\n"
            + arm_input
        )
    return prompt.replace(baseline_input, replacement, 1)


def score_contract_expectations(
    case: dict[str, Any], outputs: list[str] | None
) -> dict[str, Any] | None:
    expectations = case.get("expectations", [])
    if not expectations:
        return None
    by_key = {
        item["key"]: item
        for item in expectations
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    items = []
    for index, entry in enumerate(case["source_entries"]):
        expectation = _lookup_by_key(by_key, entry["key"])
        if expectation is None:
            continue
        output = outputs[index] if outputs and index < len(outputs) else ""
        normalized = _normalize(output)
        accepted = [_normalize(value) for value in expectation.get("accepted_outputs", [])]
        required = [
            value
            for value in expectation.get("required_substrings", [])
            if _normalize(value) not in normalized
        ]
        forbidden = [
            value
            for value in expectation.get("forbidden_substrings", [])
            if _normalize(value) in normalized
        ]
        exact_pass = not accepted or normalized in accepted
        passed = bool(output) and exact_pass and not required and not forbidden
        items.append(
            {
                **expectation,
                "source_key": entry["key"],
                "output": output,
                "exact_pass": exact_pass,
                "missing_required_substrings": required,
                "present_forbidden_substrings": forbidden,
                "passed": passed,
            }
        )
    return {
        "scored_item_count": len(items),
        "passed_item_count": sum(item["passed"] for item in items),
        "pass_rate": round(
            sum(item["passed"] for item in items) / len(items), 4
        )
        if items
        else None,
        "passed": bool(items) and all(item["passed"] for item in items),
        "items": items,
    }


def _normalize(value: str) -> str:
    return " ".join((value or "").split())


def score_key_leakage(
    case: dict[str, Any], outputs: list[str] | None
) -> dict[str, Any]:
    leaked = []
    for entry, output in zip(case["source_entries"], outputs or []):
        key = _display_key(entry["key"])
        if key in output:
            leaked.append({"source_key": entry["key"], "output": output})
    return {"passed": not leaked, "leaked_item_count": len(leaked), "items": leaked}


def score_fixture_strata(
    case: dict[str, Any],
    outputs: list[str] | None,
    structural_score: dict[str, Any],
    contract_score: dict[str, Any] | None,
) -> dict[str, Any]:
    metadata = case.get("item_metadata", {})
    if not metadata:
        return {}
    contract_items = {
        item["source_key"]: item for item in (contract_score or {}).get("items", [])
    }
    structural_items = {
        item["key"]: item for item in structural_score.get("items", [])
    }
    output_by_key = {
        entry["key"]: output
        for entry, output in zip(case["source_entries"], outputs or [])
    }
    strata: dict[str, dict[str, Any]] = {}
    for kind in ("adj_definition", "adj_reference"):
        keys = [key for key, item in metadata.items() if item["kind"] == kind]
        hard_passes = 0
        exact_gold_passes = 0
        for key in keys:
            item = structural_items.get(key)
            if item:
                has_error = any(
                    validation["level"] == "error"
                    for validation in item.get("validation", [])
                )
                hard_passes += int(item["token_parity"]["passed"] and not has_error)
            exact_gold_passes += int(
                _normalize(output_by_key.get(key, ""))
                == _normalize(metadata[key]["official_target"])
            )
        stratum = {
            "item_count": len(keys),
            "hard_pass_count": hard_passes,
            "exact_official_match_count": exact_gold_passes,
        }
        if kind == "adj_definition":
            scored = [contract_items[key] for key in keys if key in contract_items]
            stratum["definition_contract_pass_count"] = sum(
                item["passed"] for item in scored
            )
            stratum["definition_contract_passed"] = bool(scored) and all(
                item["passed"] for item in scored
            )
        else:
            stratum["exact_match_is_diagnostic_only"] = True
            reference_semantics = [
                {
                    "source_key": key,
                    "structural_grade_ceiling": reference_structural_grade_ceiling(
                        next(
                            entry["text"]
                            for entry in case["source_entries"]
                            if entry["key"] == key
                        ),
                        output_by_key.get(key, ""),
                    ),
                    **compare_reference_tokens(
                        next(
                            entry["text"]
                            for entry in case["source_entries"]
                            if entry["key"] == key
                        ),
                        output_by_key.get(key, ""),
                    ),
                }
                for key in keys
            ]
            stratum["reference_token_semantics"] = reference_semantics
            stratum["reference_contract_passed"] = all(
                item["structural_grade_ceiling"] == "FULL"
                for item in reference_semantics
            )
        strata[kind] = stratum
    return strata


def summarize_reference_strategies(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for case in cases:
        metadata = case.get("item_metadata", {})
        counts: dict[str, int] = defaultdict(int)
        for item in metadata.values():
            strategy = item.get("official_reference_strategy")
            if strategy:
                counts[strategy] += 1
        if counts:
            rows.append(
                {
                    "case_id": case["id"],
                    "target_lang": case["target_lang"],
                    "reference_count": sum(counts.values()),
                    "strategy_counts": dict(sorted(counts.items())),
                }
            )
    return rows


def run_arm_case(
    case: dict[str, Any],
    arm: ExperimentArm,
    handler: Any,
    validator: PostProcessValidator,
    *,
    repetition: int,
    run_order: int,
    request_timeout_seconds: float,
    openrouter_reasoning_effort: str | None,
) -> dict[str, Any]:
    result = {
        "id": case["id"],
        "arm_id": arm.arm_id,
        "arm_label": arm.label,
        "exploratory": arm.exploratory,
        "repetition": repetition,
        "run_order": run_order,
        "game_id": case["game_id"],
        "source_lang": case["source_lang"],
        "target_lang": case["target_lang"],
        "source_file": case["source_file"],
        "language_instruction_sha256": sha256_text(case["language_instruction"]),
        "execution_failure": None,
    }
    try:
        task = make_task(case, handler.provider_name)
        prompt = build_arm_prompt(case, handler, task, arm)
        result["prompt_text"] = prompt
        result["prompt_sha256"] = sha256_text(prompt)
        raw, outputs, elapsed, attempts, provider_attempts = call_and_parse_with_retries(
            handler,
            task,
            prompt,
            request_timeout_seconds=request_timeout_seconds,
            openrouter_reasoning_effort=openrouter_reasoning_effort,
        )
        structural_score = score_outputs(case, outputs, validator)
        contract_score = score_contract_expectations(case, outputs)
        leakage_score = score_key_leakage(case, outputs)
        strata = score_fixture_strata(
            case, outputs, structural_score, contract_score
        )
        reference_contract_passed = strata.get("adj_reference", {}).get(
            "reference_contract_passed", True
        )
        structural_score["validator_hard_pass"] = structural_score["hard_pass"]
        structural_score["hard_pass"] = (
            structural_score["hard_pass"] and reference_contract_passed
        )
        result.update(
            {
                "elapsed_seconds": round(elapsed, 3),
                "attempt_count": attempts,
                "provider_attempts": provider_attempts,
                "raw_response": raw,
                "outputs": outputs,
                "score": {
                    **structural_score,
                    "contract": contract_score,
                    "key_leakage": leakage_score,
                    "strata": strata,
                    "experiment_pass": bool(structural_score["hard_pass"])
                    and leakage_score["passed"]
                    and (contract_score is None or contract_score["passed"]),
                },
            }
        )
    except Exception as exc:
        structural_score = score_outputs(case, None, validator)
        provider_attempts = getattr(exc, "attempt_records", [])
        result.update(
            {
                "elapsed_seconds": None,
                "attempt_count": len(provider_attempts) or None,
                "provider_attempts": provider_attempts,
                "prompt_text": result.get("prompt_text"),
                "prompt_sha256": result.get("prompt_sha256"),
                "raw_response": None,
                "outputs": None,
                "score": {
                    **structural_score,
                    "contract": score_contract_expectations(case, None),
                    "key_leakage": score_key_leakage(case, None),
                    "strata": {},
                    "experiment_pass": False,
                },
                "execution_failure": f"{type(exc).__name__}: {exc}",
            }
        )
    return result


class ModelAttemptsExhausted(RuntimeError):
    def __init__(self, message: str, attempt_records: list[dict[str, Any]]):
        super().__init__(message)
        self.attempt_records = attempt_records


def _call_and_parse_once(
    handler: Any,
    task: Any,
    prompt: str,
    *,
    request_timeout_seconds: float,
    openrouter_reasoning_effort: str | None,
) -> tuple[str, list[str] | None, dict[str, Any]]:
    if handler.provider_name == "openrouter":
        raw, evidence = call_openrouter_chat_with_evidence(
            handler,
            prompt,
            reasoning_effort=openrouter_reasoning_effort,
            request_timeout_seconds=request_timeout_seconds,
        )
        parsed = handler._parse_response(
            raw, task.texts, task.file_task.target_lang["code"]
        )
        return raw, parsed, evidence
    raw, parsed, _elapsed = call_and_parse(handler, task, prompt)
    return raw, parsed, {"provider_metadata_available": False}


def call_and_parse_with_retries(
    handler: Any,
    task: Any,
    prompt: str,
    *,
    request_timeout_seconds: float = 60.0,
    openrouter_reasoning_effort: str | None = None,
) -> tuple[str, list[str], float, int, list[dict[str, Any]]]:
    """Apply production-equivalent rate limiting and retry semantics."""
    started = time.perf_counter()
    last_error: Exception | None = None
    attempt_records: list[dict[str, Any]] = []
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            rate_limiter.wait()
            raw, outputs, evidence = _call_and_parse_once(
                handler,
                task,
                prompt,
                request_timeout_seconds=request_timeout_seconds,
                openrouter_reasoning_effort=openrouter_reasoning_effort,
            )
            if outputs is None or len(outputs) != len(task.texts):
                actual = len(outputs) if outputs else 0
                raise ValueError(
                    f"Response parsing failed: expected {len(task.texts)}, got {actual}"
                )
            attempt_records.append(
                {"attempt": attempt, "status": "success", **evidence}
            )
            return (
                raw,
                outputs,
                time.perf_counter() - started,
                attempt,
                attempt_records,
            )
        except Exception as exc:
            last_error = exc
            evidence = (
                exc.evidence
                if isinstance(exc, OpenRouterAttemptError)
                else {
                    "error": {
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    }
                }
            )
            attempt_records.append(
                {"attempt": attempt, "status": "failure", **evidence}
            )
            if attempt >= MAX_RETRIES:
                break
            error = str(exc).lower()
            delay = 30 * (2 ** (attempt - 1)) if (
                "429" in error or "rate limit" in error or "too many requests" in error
            ) else attempt * 2
            time.sleep(delay)
    raise ModelAttemptsExhausted(
        f"Model call failed after {MAX_RETRIES} attempts", attempt_records
    ) from last_error


def build_schedule(
    cases: Iterable[dict[str, Any]],
    arms: Iterable[ExperimentArm],
    repetitions: int,
    seed: int,
) -> list[tuple[dict[str, Any], ExperimentArm, int]]:
    schedule = [
        (case, arm, repetition)
        for repetition in range(1, repetitions + 1)
        for case in cases
        for arm in arms
    ]
    random.Random(seed).shuffle(schedule)
    return schedule


def estimate_schedule_prompt_tokens(
    schedule: list[tuple[dict[str, Any], ExperimentArm, int]],
    handler: Any,
) -> dict[str, Any]:
    """Estimate complete prompt sizes locally without making a model request."""
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError(
            "--estimate-prompt-tokens requires the optional tiktoken package"
        ) from exc

    encoding = tiktoken.get_encoding("o200k_base")
    totals: dict[str, int] = defaultdict(int)
    calls: dict[str, int] = defaultdict(int)
    track_totals: dict[tuple[str, str], int] = defaultdict(int)
    track_calls: dict[tuple[str, str], int] = defaultdict(int)
    for case, arm, _repetition in schedule:
        task = make_task(case, handler.provider_name)
        prompt = build_arm_prompt(case, handler, task, arm)
        token_count = len(encoding.encode(prompt))
        totals[arm.arm_id] += token_count
        calls[arm.arm_id] += 1
        track = case.get("track", "mixed")
        track_totals[(track, arm.arm_id)] += token_count
        track_calls[(track, arm.arm_id)] += 1

    baseline = totals.get("A")
    cells = []
    for arm_id in sorted(totals):
        token_total = totals[arm_id]
        delta = token_total - baseline if baseline is not None else None
        cells.append(
            {
                "arm_id": arm_id,
                "call_count": calls[arm_id],
                "estimated_input_tokens": token_total,
                "mean_estimated_input_tokens": round(
                    token_total / calls[arm_id], 2
                ),
                "delta_vs_A_tokens": delta,
                "delta_vs_A_percent": round(delta / baseline * 100, 4)
                if baseline and delta is not None
                else None,
            }
        )
    track_cells = []
    for track, arm_id in sorted(track_totals):
        token_total = track_totals[(track, arm_id)]
        track_baseline = track_totals.get((track, "A"))
        delta = token_total - track_baseline if track_baseline is not None else None
        call_count = track_calls[(track, arm_id)]
        track_cells.append(
            {
                "track": track,
                "arm_id": arm_id,
                "call_count": call_count,
                "estimated_input_tokens": token_total,
                "mean_estimated_input_tokens": round(token_total / call_count, 2),
                "delta_vs_track_A_tokens": delta,
                "delta_vs_track_A_percent": round(
                    delta / track_baseline * 100, 4
                )
                if track_baseline and delta is not None
                else None,
            }
        )
    return {
        "measurement_type": "local tokenizer estimate, not provider billing",
        "encoding": "o200k_base",
        "scope": "complete rendered prompt for every scheduled call",
        "cells": cells,
        "track_cells": track_cells,
    }


def validate_schedule_prompts(
    schedule: list[tuple[dict[str, Any], ExperimentArm, int]], handler: Any
) -> None:
    """Fail before the first model request if a provider prompt is incompatible."""
    checked: set[tuple[str, str]] = set()
    for case, arm, _repetition in schedule:
        identity = (case["id"], arm.arm_id)
        if identity in checked:
            continue
        task = make_task(case, handler.provider_name)
        try:
            build_arm_prompt(case, handler, task, arm)
        except Exception as exc:
            raise ValueError(
                f"Provider {handler.provider_name!r} cannot render arm {arm.arm_id} "
                f"for case {case['id']!r}; no model calls were made"
            ) from exc
        checked.add(identity)


def render_schedule_for_batch(
    schedule: list[tuple[dict[str, Any], ExperimentArm, int]], handler: Any
) -> list[dict[str, Any]]:
    rendered = []
    for case, arm, repetition in schedule:
        task = make_task(case, handler.provider_name)
        prompt = build_arm_prompt(case, handler, task, arm)
        rendered.append(
            {
                "case_id": case["id"],
                "arm_id": arm.arm_id,
                "repetition": repetition,
                "prompt": prompt,
                "prompt_sha256": sha256_text(prompt),
            }
        )
    return rendered


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[(result["arm_id"], result["target_lang"])].append(result)
    cells = []
    for (arm_id, target_lang), items in sorted(grouped.items()):
        cells.append(
            {
                "arm_id": arm_id,
                "target_lang": target_lang,
                "run_count": len(items),
                "execution_failure_count": sum(
                    bool(item["execution_failure"]) for item in items
                ),
                "hard_pass_count": sum(item["score"]["hard_pass"] for item in items),
                "contract_pass_count": sum(
                    bool(item["score"]["contract"])
                    and item["score"]["contract"]["passed"]
                    for item in items
                ),
                "key_leakage_count": sum(
                    not item["score"]["key_leakage"]["passed"] for item in items
                ),
                "experiment_pass_count": sum(
                    item["score"]["experiment_pass"] for item in items
                ),
                "elapsed_seconds": round(
                    sum(item["elapsed_seconds"] or 0 for item in items), 3
                ),
            }
        )
    return {"run_count": len(results), "cells": cells}


def write_progress_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    """Atomically preserve completed calls so an interruption cannot erase them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)


def build_blind_artifacts(
    cases: list[dict[str, Any]], results: list[dict[str, Any]], seed: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        grouped[(result["id"], result["repetition"])].append(result)
    blind_cases = []
    mapping = []
    for (case_id, repetition), items in sorted(grouped.items()):
        candidates = []
        for item in items:
            opaque = hashlib.sha256(
                f"{seed}:{case_id}:{repetition}:{item['arm_id']}".encode("utf-8")
            ).hexdigest()[:12]
            candidates.append(
                {
                    "candidate_id": opaque,
                    "outputs": item["outputs"],
                }
            )
            mapping.append(
                {
                    "case_id": case_id,
                    "repetition": repetition,
                    "candidate_id": opaque,
                    "arm_id": item["arm_id"],
                }
            )
        random.Random(f"{seed}:{case_id}:{repetition}").shuffle(candidates)
        source_case = next(case for case in cases if case["id"] == case_id)
        blind_cases.append(
            {
                "case_id": case_id,
                "repetition": repetition,
                "game_id": source_case["game_id"],
                "source_lang": source_case["source_lang"],
                "target_lang": source_case["target_lang"],
                "source_items": [
                    {
                        "item_id": f"item-{index:02d}",
                        "source": entry["text"],
                        "official_reference": source_case.get("item_metadata", {})
                        .get(entry["key"], {})
                        .get("official_target"),
                        "kind": source_case.get("item_metadata", {})
                        .get(entry["key"], {})
                        .get("kind"),
                    }
                    for index, entry in enumerate(
                        source_case["source_entries"], start=1
                    )
                ],
                "candidates": candidates,
            }
        )
    return (
        {
            "schema_version": 1,
            "benchmark": "key-context factorial blind review",
            "manual_review_rubric": {
                "method": "Freeze judgments while candidate-to-arm mapping is hidden.",
                "definition_policy": "Exact official value is a deterministic signal.",
                "reference_policy": (
                    "Use the official target as a reference, but do not require exact "
                    "string equality when another translation is structurally valid and natural."
                ),
                "reference_grades": {
                    "FULL": (
                        "Meaning complete, target language natural, and every runtime "
                        "variable and modifier preserved."
                    ),
                    "PARTIAL": (
                        "Current static meaning and language are acceptable, but a "
                        "non-dynamic variable was deleted, hardcoded, or substituted."
                    ),
                    "FAIL": (
                        "Meaning, syntax, or format fails, or a dynamic variable loss "
                        "breaks meaning for other runtime states."
                    ),
                },
                "acceptance_boundary": (
                    "Only FULL is eligible for automatic Remis acceptance; PARTIAL "
                    "requires human review."
                ),
            },
            "cases": blind_cases,
        },
        {
            "schema_version": 1,
            "benchmark": "key-context factorial blind review",
            "mapping": mapping,
        },
    )


def _selected_arms(args: argparse.Namespace) -> list[ExperimentArm]:
    arm_ids = list(dict.fromkeys(args.arm or CORE_ARM_IDS))
    if args.include_semantic_hint and "E" not in arm_ids:
        arm_ids.append("E")
    return [ARMS[arm_id] for arm_id in arm_ids]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="lm_studio")
    parser.add_argument("--model", default="auto")
    parser.add_argument("--label", help="Human-readable model label")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument(
        "--track", choices=("adj_definition", "adj_reference")
    )
    parser.add_argument("--arm", action="append", choices=sorted(ARMS), default=[])
    parser.add_argument("--include-semantic-hint", action="store_true")
    parser.add_argument(
        "--official-country-tags",
        type=Path,
        default=DEFAULT_OFFICIAL_COUNTRY_TAGS,
        help="Frozen official Victoria 3 country TAG catalog used by arm F",
    )
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--seed", type=int, default=207)
    parser.add_argument(
        "--max-model-calls",
        type=int,
        default=500,
        help="Safety ceiling for non-dry runs; raise explicitly for larger experiments",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--estimate-prompt-tokens",
        action="store_true",
        help="During dry-run, render prompts and estimate input tokens with o200k_base",
    )
    parser.add_argument(
        "--estimate-luna-batch-cost",
        action="store_true",
        help="Project Luna batch cost from local tokens and frozen Aventine ratios",
    )
    parser.add_argument(
        "--prepare-openrouter-batch",
        type=Path,
        help="Write a no-call OpenRouter batch manifest during dry-run",
    )
    parser.add_argument(
        "--batch-reasoning-effort",
        choices=("medium", "high"),
        default="high",
    )
    parser.add_argument(
        "--lexical-control-fixture",
        type=Path,
        help="Attach one frozen glossary control identically to every experiment arm",
    )
    parser.add_argument(
        "--confirm-model-usage",
        action="store_true",
        help="Required for any run that may call a paid or local model",
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=float,
        default=60.0,
        help="Per-attempt OpenRouter timeout for benchmark calls",
    )
    parser.add_argument(
        "--openrouter-reasoning-effort",
        choices=("none", "minimal", "low", "medium", "high"),
        default="none",
        help="Explicit OpenRouter reasoning effort recorded with the experiment",
    )
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.max_model_calls < 1:
        parser.error("--max-model-calls must be at least 1")
    if not 5 <= args.request_timeout_seconds <= 300:
        parser.error("--request-timeout-seconds must be between 5 and 300")
    if args.estimate_luna_batch_cost and not args.estimate_prompt_tokens:
        parser.error(
            "--estimate-luna-batch-cost requires --estimate-prompt-tokens"
        )
    if args.prepare_openrouter_batch and not args.dry_run:
        parser.error("--prepare-openrouter-batch is a dry-run preparation action")
    if not args.dry_run and not args.confirm_model_usage:
        parser.error("Model execution requires --confirm-model-usage")

    fixture, fixture_hash = read_factorial_fixture(args.fixture)
    cases = resolve_factorial_cases(
        fixture, OFFICIAL_LANGUAGE_POLICIES, set(args.case)
    )
    arms = _selected_arms(args)
    if any(arm.include_detected_semantic_hint for arm in arms):
        cases = attach_detected_semantic_hints(
            cases, load_official_country_tags(args.official_country_tags)
        )
    if any(arm.include_language_specific_semantic_hint for arm in arms):
        cases = attach_language_specific_semantic_hints(
            cases, load_official_country_tags(args.official_country_tags)
        )
    lexical_control = None
    if args.lexical_control_fixture:
        entries, control_raw = load_lexical_control(args.lexical_control_fixture)
        cases = attach_lexical_control(cases, entries)
        lexical_control = {
            "path": str(args.lexical_control_fixture.resolve()),
            "sha256": sha256_text(control_raw),
            "entry_count": len(entries),
            "scope": "shared identically by all arms",
        }
    elif isinstance(fixture.get("lexical_control"), dict):
        lexical_control = {
            "path": str(args.fixture.resolve()),
            "sha256": fixture_hash,
            "entry_count": len(fixture["lexical_control"].get("entries", [])),
            "scope": "embedded control shared identically by all arms",
        }
    if args.track:
        cases = [case for case in cases if case.get("track") == args.track]
        if not cases:
            parser.error(f"No cases matched --track {args.track}")
    schedule = build_schedule(cases, arms, args.repetitions, args.seed)
    if not args.dry_run and len(schedule) > args.max_model_calls:
        parser.error(
            f"Planned {len(schedule)} model calls, above --max-model-calls "
            f"{args.max_model_calls}"
        )

    if args.dry_run:
        token_estimate = None
        if args.estimate_prompt_tokens:
            dry_model = args.model if args.model != "auto" else "benchmark-dry-run"
            dry_handler = get_handler(args.provider, model_name=dry_model)
            token_estimate = estimate_schedule_prompt_tokens(schedule, dry_handler)
        luna_batch_cost = (
            estimate_luna_batch_cost(token_estimate)
            if args.estimate_luna_batch_cost and token_estimate
            else None
        )
        batch_manifest_path = None
        if args.prepare_openrouter_batch:
            dry_handler = dry_handler if args.estimate_prompt_tokens else get_handler(
                "lm_studio", model_name="benchmark-dry-run"
            )
            manifest = build_openrouter_batch_manifest(
                render_schedule_for_batch(schedule, dry_handler),
                args.batch_reasoning_effort,
            )
            args.prepare_openrouter_batch.parent.mkdir(parents=True, exist_ok=True)
            args.prepare_openrouter_batch.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            batch_manifest_path = str(args.prepare_openrouter_batch.resolve())
        print(
            json.dumps(
                {
                    "benchmark": fixture_name(fixture),
                    "fixture_sha256": fixture_hash,
                    "seed": args.seed,
                    "repetitions": args.repetitions,
                    "arms": [arm.__dict__ for arm in arms],
                    "lexical_control": lexical_control,
                    "case_count": len(cases),
                    "planned_model_call_count": len(schedule),
                    "prompt_token_estimate": token_estimate,
                    "luna_batch_cost_estimate": luna_batch_cost,
                    "openrouter_batch_manifest": batch_manifest_path,
                    "official_reference_strategy_summary": (
                        summarize_reference_strategies(cases)
                    ),
                    "run_order": [
                        {
                            "case_id": case["id"],
                            "target_lang": case["target_lang"],
                            "arm_id": arm.arm_id,
                            "repetition": repetition,
                        }
                        for case, arm, repetition in schedule
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.model == "auto":
        model_id = discover_single_model(get_handler(args.provider))
    else:
        model_id = args.model
    handler = get_handler(args.provider, model_name=model_id)
    validate_schedule_prompts(schedule, handler)
    validator = PostProcessValidator()
    glossary_manager.in_memory_glossary = {"entries": []}

    run_started_at = datetime.now(timezone.utc)
    timestamp = run_started_at.strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{timestamp}_{slugify(args.label or model_id)}"
    checkpoint_path = args.output_dir / f"{stem}_checkpoint.json"
    checkpoint_base = {
        "schema_version": 1,
        "benchmark": fixture_name(fixture),
        "fixture_sha256": fixture_hash,
        "provider": args.provider,
        "model_id": model_id,
        "model_label": args.label or model_id,
        "started_at_utc": run_started_at.isoformat(),
        "planned_run_count": len(schedule),
        "request_timeout_seconds": args.request_timeout_seconds,
        "openrouter_reasoning_effort": args.openrouter_reasoning_effort,
    }
    results: list[dict[str, Any]] = []
    write_progress_checkpoint(
        checkpoint_path,
        {**checkpoint_base, "status": "in_progress", "results": results},
    )
    print(json.dumps({"checkpoint": str(checkpoint_path)}), flush=True)
    try:
        for index, (case, arm, repetition) in enumerate(schedule, start=1):
            result = run_arm_case(
                case,
                arm,
                handler,
                validator,
                repetition=repetition,
                run_order=index,
                request_timeout_seconds=args.request_timeout_seconds,
                openrouter_reasoning_effort=(
                    None
                    if args.openrouter_reasoning_effort == "none"
                    else args.openrouter_reasoning_effort
                ),
            )
            results.append(result)
            write_progress_checkpoint(
                checkpoint_path,
                {
                    **checkpoint_base,
                    "status": "in_progress",
                    "completed_run_count": len(results),
                    "results": results,
                },
            )
            print(
                json.dumps(
                    {
                        "completed": len(results),
                        "planned": len(schedule),
                        "case_id": case["id"],
                        "arm_id": arm.arm_id,
                        "execution_failure": result["execution_failure"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    except KeyboardInterrupt:
        write_progress_checkpoint(
            checkpoint_path,
            {
                **checkpoint_base,
                "status": "interrupted",
                "completed_run_count": len(results),
                "results": results,
            },
        )
        raise
    now = datetime.now(timezone.utc)
    report = {
        "schema_version": 1,
        "benchmark": fixture_name(fixture),
        "fixture_sha256": fixture_hash,
        "corpus_fingerprint_sha256": fixture.get("corpus_fingerprint_sha256"),
        "created_at_utc": now.isoformat(),
        "provider": args.provider,
        "model_id": model_id,
        "model_label": args.label or model_id,
        "request_timeout_seconds": args.request_timeout_seconds,
        "openrouter_reasoning_effort": args.openrouter_reasoning_effort,
        "seed": args.seed,
        "repetitions": args.repetitions,
        "arms": [arm.__dict__ for arm in arms],
        "lexical_control": lexical_control,
        "analysis_policy": {
            "primary_design": "2x2 factorial: raw key absent/present x language policy absent/present",
            "primary_arms": list(CORE_ARM_IDS),
            "exploratory_arms": (
                "E/F/G/H/H2 are excluded from primary A-D factorial claims; F uses "
                "deterministic official-country routing and G retests raw key plus "
                "language policy; H combines deterministic routing with language "
                "policy while withholding raw keys; H2 replaces H's generic form "
                "with a target-language runtime-form contract. All share entry isolation"
            ),
            "paired_unit": "same model, fixture case, and repetition",
            "outcomes": [
                "hard structural validity",
                "target-language contract expectations",
                "key leakage",
                "blind language-quality review",
                "latency",
            ],
            "track_policy": {
                "adj_definition": (
                    "Exact official definition is gold; compare value-only, raw-key, "
                    "and semantic-contract treatments separately."
                ),
                "adj_reference": (
                    "Keep the full protected token strict in production scoring. "
                    "Official rewrites are linguistic references, not automatic "
                    "structure gold."
                ),
            },
            "usage_boundary": (
                "For OpenRouter benchmark calls, every attempt persists the sanitized "
                "completion response, router metadata, provider-native usage/cost, and "
                "generation lookup when available. Other providers retain only the "
                "legacy text-level evidence."
            ),
        },
        "summary": summarize_results(results),
        "composition": score_composition_results(fixture, cases, results),
        "results": results,
    }
    blind, mapping = build_blind_artifacts(cases, results, args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / f"{stem}_factorial.json"
    blind_path = args.output_dir / f"{stem}_blind.json"
    mapping_path = args.output_dir / f"{stem}_blind-key.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    blind_path.write_text(
        json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    mapping_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_progress_checkpoint(
        checkpoint_path,
        {
            **checkpoint_base,
            "status": "complete",
            "completed_run_count": len(results),
            "report": str(report_path),
            "results": results,
        },
    )
    print(
        json.dumps(
            {
                "report": str(report_path),
                "blind_review": str(blind_path),
                "blind_key_written": True,
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
