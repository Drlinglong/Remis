"""Offline translation and blind-judge runner for archive-context A/B cases."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from collections import Counter
import json
import math
import random
import re
from typing import Any, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from scripts.developer_tools.archive_ab_contract import (
    ArchiveCase,
    Candidate,
    Recipe,
    Scenario,
    SourceEntry,
    Usage,
    canonical_json,
    case_manifest,
    sha256_text,
    ERROR_TAGS,
    HARD_ERROR_TAGS,
)


PLACEHOLDER_PATTERN = re.compile(r"(?:\$[^$\n]+\$|\[[^\]\n]+\]|£[^£\n]+£|§[^§\n]+§)")


class TranslationProvider(Protocol):
    def translate(self, prompt: str, *, case_id: str, request_id: str) -> tuple[Mapping[str, str], Usage]: ...


JudgePayload = Mapping[str, Any] | str
JudgeResponse = tuple[JudgePayload, Usage]


class Judge(Protocol):
    def judge(self, prompt: str) -> JudgeResponse: ...


@dataclass(frozen=True)
class HardCheck:
    passed: bool
    error_tags: tuple[str, ...] = ()
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class TranslationPair:
    case: ArchiveCase
    candidate_a: Candidate | None
    candidate_b: Candidate | None
    skipped: bool = False
    skip_reason: str = ""
    scenario: Scenario | None = None
    execution_order: tuple[str, str] = ("A", "B")
    request_fingerprints: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BlindResult:
    case_id: str
    winner: str
    confidence: float
    error_tags: tuple[str, ...]
    evidence: tuple[str, ...]
    presentation_winners: tuple[str, str]
    presentation_orders: tuple[tuple[str, str], tuple[str, str]]
    needs_adjudication: bool
    hard_checks: Mapping[str, HardCheck]
    usage: Usage = Usage()
    translation_usage_by_arm: Mapping[str, Usage] = field(default_factory=dict)
    judge_usage: Usage = Usage()
    error_tags_by_arm: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


class JudgeOutput(BaseModel):
    """Strict, provider-independent schema for the double-blind judge."""

    model_config = ConfigDict(extra="forbid", strict=True)

    winner: Literal["A", "B", "tie"]
    confidence: float = Field(ge=0.0, le=1.0)
    error_tags: list[str]
    evidence: list[str]
    candidate_error_tags: dict[str, list[str]]

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("confidence must be finite")
        return value

    @field_validator("error_tags")
    @classmethod
    def error_tags_must_be_allowlisted(cls, values: list[str]) -> list[str]:
        invalid = set(values) - (ERROR_TAGS | HARD_ERROR_TAGS)
        if invalid:
            raise ValueError(f"unknown judge error tags: {sorted(invalid)}")
        return values

    @field_validator("candidate_error_tags")
    @classmethod
    def candidate_error_tags_must_be_allowlisted(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        invalid_arms = set(values) - {"A", "B"}
        if set(values) != {"A", "B"}:
            raise ValueError("candidate_error_tags must include both A and B")
        invalid_tags = {tag for tags in values.values() for tag in tags} - (ERROR_TAGS | HARD_ERROR_TAGS)
        if invalid_arms or invalid_tags:
            raise ValueError(f"invalid candidate error tags: arms={sorted(invalid_arms)}, tags={sorted(invalid_tags)}")
        return values


def _placeholders(text: str) -> Counter[str]:
    return Counter(PLACEHOLDER_PATTERN.findall(text))


def _protected_tokens(text: str, pattern: str) -> tuple[str, ...]:
    return tuple(re.findall(pattern, text))


def _strict_contract_errors(source: str, translation: str) -> tuple[set[str], list[str]]:
    tags: set[str] = set()
    details: list[str] = []
    if not translation.strip():
        tags.add("empty_translation")
        details.append("translation is empty")
    if source.count("\n") != translation.count("\n"):
        tags.add("newline_mismatch")
        details.append("newline count differs")
    if Counter(_protected_tokens(source, r"\\.")) != Counter(_protected_tokens(translation, r"\\.")):
        tags.add("escape_mismatch")
        details.append("escape sequence differs")
    protected = {
        "dynamic_variable_mismatch": r"\[[^\]\n]+\]",
        "color_tag_mismatch": r"§(?:[A-Za-z]|!)",
        "icon_mismatch": r"(?:£[^£\n]+£|@[A-Za-z0-9_.-]+!)",
        "format_marker_mismatch": r"(?:#[A-Za-z0-9_]+|#!)",
    }
    for tag, pattern in protected.items():
        if Counter(_protected_tokens(source, pattern)) != Counter(_protected_tokens(translation, pattern)):
            tags.add(tag)
            details.append(f"{tag} differs")
    return tags, details


def hard_check(case: ArchiveCase, translations: Mapping[str, str]) -> HardCheck:
    expected = set(case.member_source_ids)
    actual = set(translations)
    tags: set[str] = set()
    details: list[str] = []
    if actual != expected:
        if expected - actual:
            tags.add("missing_source_id")
            details.append(f"missing={sorted(expected - actual)}")
        if actual - expected:
            tags.add("extra_source_id")
            details.append(f"extra={sorted(actual - expected)}")
    for entry in case.source_entries:
        if entry.source_id not in translations:
            continue
        translation = "" if translations[entry.source_id] is None else str(translations[entry.source_id])
        contract_tags, contract_details = _strict_contract_errors(entry.text, translation)
        if contract_tags:
            tags.update(contract_tags)
            details.extend(f"{entry.source_id}: {detail}" for detail in contract_details)
        if _placeholders(entry.text) != _placeholders(translation):
            tags.add("placeholder_mismatch")
            details.append(f"placeholder={entry.source_id}")
    if case.dataset_id.startswith("stellaris:"):
        from scripts.utils.post_process_validator import PostProcessValidator, ValidationLevel

        validator = PostProcessValidator()
        for entry in case.source_entries:
            if entry.source_id not in translations:
                continue
            validation = validator.validate_entry(
                "stellaris", entry.key, str(translations[entry.source_id]), source_value=entry.text,
            )
            if any(item.level == ValidationLevel.ERROR for item in validation):
                tags.add("postprocess_validation_error")
                details.append(f"postprocess={entry.source_id}")
    if len(actual) != len(expected):
        tags.add("entry_count_mismatch")
    return HardCheck(not tags, tuple(sorted(tags)), tuple(details))


def build_prompt(case: ArchiveCase, recipe: Recipe, arm: str) -> str:
    """Build one common prompt; only the archive context differs by arm."""

    lines = [
        "Translate this complete evaluation case as a professional game localizer.",
        "Preserve keys, variables, placeholders, formatting, entry count, and causal meaning.",
        f"Prompt contract: {recipe.prompt_version}.",
        "Glossary: " + canonical_json(dict(recipe.glossary)),
        "Adjacent source context: " + " ".join(case.adjacent_source_text),
        "Source entries (keep this order):",
    ]
    lines.extend(f"- {entry.source_id}: {entry.text}" for entry in case.source_entries)
    if arm == "B" and case.persisted_archive_context:
        archive = case.persisted_archive_context
        lines.extend([
            "Archive context (the only A/B difference):",
            f"Persisted Remis archive artifact: {archive}",
        ])
    else:
        lines.append("Archive context: none")
    return "\n".join(lines)


def _validate_scenario(case: ArchiveCase, scenario: Scenario) -> None:
    if scenario.kind == "incremental" and not scenario.changed_source_ids:
        raise ValueError("incremental scenario requires changed source IDs")


def translate_pair(
    case: ArchiveCase,
    recipe: Recipe,
    scenario: Scenario,
    provider: TranslationProvider,
) -> TranslationPair:
    _validate_scenario(case, scenario)
    effective_case = case
    if scenario.archive_mode == "none":
        effective_case = replace(
            case, mod_summary="", matched_chain_context="", wiki_context="",
            persisted_archive_context="", persisted_old_archive_context="",
            persisted_archive_metadata={}, persisted_old_archive_metadata={},
        )
    elif scenario.archive_mode == "stale":
        effective_case = replace(
            case, mod_summary=case.old_mod_summary or case.mod_summary, matched_chain_context="", wiki_context="",
        )
    changed = scenario.changed_source_ids or case.changed_source_ids
    if scenario.kind == "incremental" and not (set(case.member_source_ids) & set(changed)):
        return TranslationPair(case, None, None, True, "unchanged_case", scenario)
    if scenario.archive_mode in {"fresh", "stale"}:
        archive_context = effective_case.persisted_archive_context if scenario.archive_mode == "fresh" else effective_case.persisted_old_archive_context
        archive_metadata = effective_case.persisted_archive_metadata if scenario.archive_mode == "fresh" else effective_case.persisted_old_archive_metadata
        if not archive_context:
            return TranslationPair(case, None, None, True, "missing_persisted_archive_artifact", scenario)
        effective_case = replace(effective_case, persisted_archive_context=archive_context, persisted_archive_metadata=archive_metadata)
    rng = random.Random(recipe.seed ^ int(sha256_text(case.case_id)[:8], 16))
    execution_order = ["A", "B"]
    rng.shuffle(execution_order)
    prompts = {arm: build_prompt(effective_case, recipe, arm) for arm in ("A", "B")}
    translations: dict[str, Candidate] = {}
    fingerprints = {}
    for execution_index, arm in enumerate(execution_order):
        request_id = "archive-ab-request-" + sha256_text(canonical_json({
            "case_id": case.case_id,
            "execution_index": execution_index,
            "recipe": recipe.request_fingerprint,
        }))[:24]
        values, usage = provider.translate(prompts[arm], case_id=case.case_id, request_id=request_id)
        prompt_hash = sha256_text(prompts[arm])
        fingerprints[arm] = sha256_text(canonical_json({"recipe": recipe.request_fingerprint, "case_id": case.case_id, "arm": arm, "prompt": prompt_hash}))
        translations[arm] = Candidate(arm, dict(values), usage, prompt_hash, fingerprints[arm])
    return TranslationPair(case, translations["A"], translations["B"], scenario=scenario, execution_order=tuple(execution_order), request_fingerprints=fingerprints)


def _judge_prompt(case: ArchiveCase, candidates: Mapping[str, Mapping[str, str]]) -> str:
    lines = [
        "You are a professional game-localization proofreader. Return JSON only.",
        "Compare the complete chain or complete semantic batch, not individual entry votes.",
        "Assess fidelity, referents, entities, causality, branches, terminology, and fluency.",
        "Return winner (A/B/tie), confidence (0..1), error_tags, candidate_error_tags for both A and B, and concise evidence.",
        f"Case kind: {case.case_kind}; case ID: {case.case_id}.",
        "Official source:",
    ]
    lines.extend(f"- {entry.source_id}: {entry.text}" for entry in case.source_entries)
    lines.append("Gold story facts: " + " | ".join(case.gold_facts))
    lines.append("Wiki evidence IDs: " + ", ".join(case.wiki_evidence_ids))
    lines.append("Judge-only Wiki fact context: " + (case.wiki_context or "none"))
    for label in ("A", "B"):
        lines.append(f"Candidate {label}: {canonical_json(dict(candidates[label]))}")
    return "\n".join(lines)


def _parse_judgment(value: Mapping[str, Any] | str) -> tuple[str, float, tuple[str, ...], tuple[str, ...], Mapping[str, tuple[str, ...]]]:
    try:
        parsed = JudgeOutput.model_validate_json(value) if isinstance(value, str) else JudgeOutput.model_validate(value)
    except (TypeError, ValueError, ValidationError) as exc:
        raise ValueError(f"judge output failed strict schema validation: {exc}") from exc
    return parsed.winner, parsed.confidence, tuple(sorted(set(parsed.error_tags))), tuple(parsed.evidence), {
        arm: tuple(sorted(tags)) for arm, tags in parsed.candidate_error_tags.items()
    }


def _call_judge(judge: Judge, prompt: str) -> tuple[Mapping[str, Any] | str, Usage]:
    response = judge.judge(prompt)
    if not isinstance(response, tuple) or len(response) != 2 or not isinstance(response[1], Usage):
        raise ValueError("judge adapter must return (payload, Usage)")
    return response[0], response[1]


def _map_presented_winner(value: str, order: tuple[str, str]) -> str:
    normalized = value.lower()
    return "tie" if normalized == "tie" else order[0 if normalized == "a" else 1]


def blind_judge(case: ArchiveCase, pair: TranslationPair, judge: Judge, seed: int = 198) -> BlindResult:
    if pair.skipped or pair.candidate_a is None or pair.candidate_b is None:
        raise ValueError(f"cannot judge skipped case: {case.case_id}")
    checks = {"A": hard_check(case, pair.candidate_a.translations), "B": hard_check(case, pair.candidate_b.translations)}
    translation_usage = {"A": pair.candidate_a.usage, "B": pair.candidate_b.usage}
    if not checks["A"].passed or not checks["B"].passed:
        winner = "tie" if checks["A"].passed == checks["B"].passed else ("A" if checks["A"].passed else "B")
        return BlindResult(case.case_id, winner, 1.0, tuple(sorted(set(checks["A"].error_tags + checks["B"].error_tags))), (), (winner, winner), (("A", "B"), ("B", "A")), False, checks, pair.candidate_a.usage + pair.candidate_b.usage, translation_usage, Usage(), {"A": checks["A"].error_tags, "B": checks["B"].error_tags})
    rng = random.Random(seed)
    order = ["A", "B"]
    rng.shuffle(order)
    actual = {"A": pair.candidate_a.translations, "B": pair.candidate_b.translations}
    reverse = (order[1], order[0])
    judge_usage = Usage()
    try:
        first_payload, first_usage = _call_judge(judge, _judge_prompt(case, {label: actual[arm] for label, arm in zip(("A", "B"), order)}))
        judge_usage += first_usage
        first = _parse_judgment(first_payload)
        second_payload, second_usage = _call_judge(judge, _judge_prompt(case, {label: actual[arm] for label, arm in zip(("A", "B"), reverse)}))
        judge_usage += second_usage
        second = _parse_judgment(second_payload)
    except ValueError as exc:
        translation_total = pair.candidate_a.usage + pair.candidate_b.usage
        return BlindResult(case.case_id, "tie", 0.0, (), (str(exc),), ("tie", "tie"), (tuple(order), reverse), True, checks, translation_total + judge_usage, translation_usage, judge_usage, {"A": checks["A"].error_tags, "B": checks["B"].error_tags})
    mapped = (_map_presented_winner(first[0], tuple(order)), _map_presented_winner(second[0], reverse))
    stable = mapped[0] == mapped[1]
    winner = mapped[0] if stable else "tie"
    tags = tuple(sorted(set(first[2] + second[2])))
    evidence = tuple(dict.fromkeys(first[3] + second[3]))
    arm_errors = {"A": set(checks["A"].error_tags), "B": set(checks["B"].error_tags)}
    for parsed, presented_order in ((first, order), (second, reverse)):
        for label, values in parsed[4].items():
            arm_errors[presented_order[0 if label == "A" else 1]].update(values)
    translation_total = pair.candidate_a.usage + pair.candidate_b.usage
    return BlindResult(case.case_id, winner, min(first[1], second[1]), tags, evidence, mapped, (tuple(order), reverse), not stable, checks, translation_total + judge_usage, translation_usage, judge_usage, {arm: tuple(sorted(values)) for arm, values in arm_errors.items()})


def build_run_manifest(
    pairs: list[TranslationPair], results: list[BlindResult], recipe: Recipe, scenario: Scenario,
    *, source_files: list[Mapping[str, Any]], gold_files: list[Mapping[str, Any]], wiki_sources: list[Mapping[str, Any]],
    wiki_package: Mapping[str, Any] | None = None, archive_artifacts: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    scenario_payload = asdict(scenario)
    scenario_payload["changed_source_ids"] = sorted(scenario.changed_source_ids)
    return {
        "schema_version": "remis-archive-ab-run-v1",
        "protocol": {"recipe": asdict(recipe), "recipe_hash": recipe.fingerprint, "scenario": scenario_payload},
        "source_files": source_files,
        "gold_files": gold_files,
        "wiki_package": dict(wiki_package or {}),
        "wiki_sources": wiki_sources,
        "archive_artifacts": list(archive_artifacts or []),
        "cases": [case_manifest(pair.case) | {"skipped": pair.skipped, "skip_reason": pair.skip_reason} for pair in pairs],
        "judgments": [asdict(result) for result in results],
        "arm_randomization": {result.case_id: [list(order) for order in result.presentation_orders] for result in results},
        "execution_order": {pair.case.case_id: list(pair.execution_order) for pair in pairs},
        "request_fingerprints": {pair.case.case_id: dict(pair.request_fingerprints) for pair in pairs},
        "prompt_hashes": {
            pair.case.case_id: {
                "A": pair.candidate_a.prompt_hash if pair.candidate_a else None,
                "B": pair.candidate_b.prompt_hash if pair.candidate_b else None,
            }
            for pair in pairs
        },
        "usage": {
            result.case_id: {
                "translation_by_arm": {
                    arm: usage.as_dict() for arm, usage in result.translation_usage_by_arm.items()
                },
                "judge": result.judge_usage.as_dict(),
                "total": result.usage.as_dict(),
                "archive_generation": Usage().as_dict(),
            }
            for result in results
        },
    }


def semantic_identity_by_arm(scenario: Scenario) -> dict[str, dict[str, str]]:
    """Describe the experimental meaning of each arm only after reveal."""

    archive_label = "baseline(no archive)" if scenario.archive_mode == "none" else f"archive({scenario.archive_mode})"
    archive_role = "baseline" if scenario.archive_mode == "none" else "archive"
    return {
        "A": {"label": "baseline(no archive)", "role": "baseline", "archive_mode": "none"},
        "B": {"label": archive_label, "role": archive_role, "archive_mode": scenario.archive_mode},
    }


__all__ = [
    "BlindResult", "HardCheck", "Judge", "TranslationPair", "TranslationProvider",
    "blind_judge", "build_prompt", "build_run_manifest", "hard_check", "semantic_identity_by_arm", "translate_pair",
]
