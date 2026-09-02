from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import pytest

from scripts.developer_tools.archive_ab_contract import ArchiveCase, Recipe, Scenario, SourceEntry, Usage
from scripts.developer_tools.archive_ab_fixtures import load_cases
from scripts.developer_tools import archive_ab_fixtures
from scripts.developer_tools.archive_ab_review_queue import (
    build_review_payload,
    developer_review_enabled,
    make_review_record,
    make_reveal_record,
    review_summary,
    sample_case_ids,
    reveal_review_payload,
)
from scripts.developer_tools.archive_ab_runner import blind_judge, hard_check, translate_pair
from scripts.developer_tools.archive_ab_scorer import summarize


class FakeProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def translate(self, prompt: str, *, case_id: str, request_id: str):
        self.calls.append((case_id, request_id, prompt))
        marker = "欠佳" if "Persisted Remis archive artifact:" in prompt else "优质"
        return {line.split(": ", 1)[0][2:]: f"{marker} {line.split(': ', 1)[1]}" for line in prompt.splitlines() if line.startswith("- source-")}, Usage(input_tokens=10, output_tokens=5, cost_usd=0.01)


class ContentJudge:
    def judge(self, prompt: str):
        payload = {"winner": "A" if "优质" in prompt.split('Candidate A:', 1)[1].split('Candidate B:', 1)[0] else "B", "confidence": 0.9, "error_tags": [], "evidence": ["The first presented candidate preserves the complete story better."], "candidate_error_tags": {"A": [], "B": []}}
        return payload, Usage(input_tokens=20, output_tokens=5, cost_usd=0.002)


class InvalidJudge:
    def judge(self, prompt: str):
        return {"winner": "maybe", "confidence": float("nan"), "error_tags": ["not-allowlisted"], "evidence": ["invalid"], "candidate_error_tags": {"A": [], "B": []}}, Usage(cost_usd=0.001)


def make_case(case_kind: str = "event_chain", wiki_context: str = "") -> ArchiveCase:
    return ArchiveCase(
        case_id="case-1", dataset_id="fixture:demo", case_kind=case_kind,
        chain_id="chain-1" if case_kind == "event_chain" else None,
        reference_batch_id="batch-1" if case_kind == "reference_batch" else None,
        source_entries=(
            SourceEntry("source-1:0", "source-1", 0, "A signal for $name$", "unit-1", "group-1"),
            SourceEntry("source-2:0", "source-2", 0, "The signal returns.", "unit-2", "group-2"),
        ),
        gold_facts=("The signal returns to the same story.",), wiki_evidence_ids=("wiki-1",), wiki_context=wiki_context,
        mod_summary="A short mod summary.", matched_chain_context="The signal's return is causal.",
        old_mod_summary="An old summary without the event chain.",
        persisted_archive_context="Persisted current archive: the signal returns causally.",
        persisted_old_archive_context="Persisted old archive: an unusual anomaly returns.",
    )


def test_hard_check_is_deterministic_and_placeholder_safe():
    case = make_case()
    assert hard_check(case, {entry.source_id: f"译 {entry.text}" for entry in case.source_entries}).passed
    check = hard_check(case, {"source-1:0": "译 name"})
    assert not check.passed
    assert set(check.error_tags) == {"missing_source_id", "placeholder_mismatch", "entry_count_mismatch"}


def test_two_arms_share_recipe_and_only_fresh_archive_context_differs():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1", glossary={"signal": "信号"})
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    assert len(provider.calls) == 2
    assert all("A" not in item[1] and "B" not in item[1] for item in provider.calls)
    assert "Archive context: none" in next(item[2] for item in provider.calls if "Archive context: none" in item[2])
    assert "Persisted Remis archive artifact: Persisted current archive" in next(item[2] for item in provider.calls if "Persisted Remis archive artifact:" in item[2])
    assert pair.candidate_a is not None and pair.candidate_b is not None


def test_fresh_archive_prompt_uses_persisted_archive_not_wiki_oracle():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v2")
    pair = translate_pair(make_case(wiki_context="Judge-only Wiki facts"), recipe, Scenario("initial", "fresh"), provider)
    assert "Persisted Remis archive artifact: Persisted current archive" in next(item[2] for item in provider.calls if "Persisted Remis archive artifact:" in item[2])
    assert all("Judge-only Wiki facts" not in item[2] for item in provider.calls)


def test_stale_and_none_archive_context_exclude_current_wiki_facts():
    case = make_case(wiki_context="Current Wiki facts")
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v2")
    provider = FakeProvider()
    translate_pair(case, recipe, Scenario("initial", "none"), provider)
    assert all("Current Wiki facts" not in call[2] for call in provider.calls)
    assert all("Persisted Remis archive artifact:" not in call[2] for call in provider.calls)
    provider.calls.clear()
    translate_pair(case, recipe, Scenario("incremental", "stale", frozenset({"source-1:0"})), provider)
    assert all("Current Wiki facts" not in call[2] for call in provider.calls)


def test_stale_incremental_skips_unchanged_and_excludes_old_chain_from_changed_case():
    case = make_case()
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    unchanged = translate_pair(case, recipe, Scenario("incremental", "stale", frozenset({"other:0"})), provider)
    assert unchanged.skipped and not provider.calls
    changed = translate_pair(case, recipe, Scenario("incremental", "stale", frozenset({"source-1:0"})), provider)
    assert not changed.skipped
    assert all("The signal's return is causal." not in call[2] for call in provider.calls)
    assert all("Persisted Remis archive artifact: Persisted old archive" in call[2] for call in provider.calls if "Persisted Remis archive artifact:" in call[2])


def test_blind_judge_presents_same_case_in_reverse_and_maps_actual_arm():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge(), seed=198)
    assert result.winner == "A"
    assert result.presentation_orders[1] == tuple(reversed(result.presentation_orders[0]))
    assert result.presentation_winners == ("A", "A")
    assert not result.needs_adjudication
    assert result.judge_usage.cost_usd == 0.004
    assert result.usage.cost_usd == 0.024


def test_invalid_judge_schema_enters_adjudication_instead_of_defaulting_tie():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, InvalidJudge())
    assert result.needs_adjudication
    assert result.winner == "tie"
    assert result.confidence == 0.0
    assert any("strict schema" in item for item in result.evidence)
    assert result.judge_usage.cost_usd == 0.001


def test_hard_check_rejects_empty_and_protected_token_corruption():
    case = ArchiveCase(
        case_id="protected", dataset_id="fixture:demo", case_kind="event_chain", chain_id="chain", reference_batch_id=None,
        source_entries=(SourceEntry("source:0", "source", 0, "Line $var$\\n§H[From.GetName]§! £energy£ @icon!", "unit", "group"),),
    )
    result = hard_check(case, {"source:0": ""})
    assert not result.passed
    assert "empty_translation" in result.error_tags
    result = hard_check(case, {"source:0": "Line $other$\\t§H[From.GetName]§! £energy£ @icon!"})
    assert {"placeholder_mismatch", "escape_mismatch"}.issubset(result.error_tags)


def test_cli_dry_run_uses_safe_marker_and_asserts_hard_checks(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "none.json"
    completed = subprocess.run(
        [sys.executable, "scripts/developer_tools/run_archive_ab_benchmark.py", "--dry-run", "--archive-mode", "none", "--output", str(output)],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["review_cases"]) == 3
    assert all(check["passed"] for result in payload["manifest"]["judgments"] for check in result["hard_checks"].values())
    assert all("dry-run-A" not in json.dumps(item) and "dry-run-B" not in json.dumps(item) for item in payload["review_cases"])
    recipe = payload["manifest"]["protocol"]["recipe"]
    assert {key for key in ("provider_revision", "temperature", "top_p", "seed", "request_fingerprint") if key in recipe} == {
        "provider_revision", "temperature", "top_p", "seed", "request_fingerprint",
    }
    assert all(set(order) == {"A", "B"} for order in payload["manifest"]["execution_order"].values())


def test_judge_schema_requires_per_arm_error_maps():
    from scripts.developer_tools.archive_ab_runner import JudgeOutput

    with pytest.raises(ValueError):
        JudgeOutput.model_validate({"winner": "tie", "confidence": 0, "error_tags": [], "evidence": []})


def test_published_archive_release_is_loaded_from_local_remis_api(monkeypatch):
    payload = {
        "release": {
            "release_id": "release-1",
            "source_snapshot_hash": "snapshot-1",
            "created_at": "2026-09-03T00:00:00Z",
        },
        "effective_context": {"chain:horizon_signal": {"summary": "Persisted release context"}},
    }

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    requests = []
    monkeypatch.setattr(archive_ab_fixtures, "urlopen", lambda request, timeout: (requests.append((request.full_url, timeout)) or Response()))
    root = Path(r"J:\remis-aventine-benchmark-corpus")
    cases, provenance = load_cases(
        Path("tests/fixtures/remis_archive_ab_v1/cases.json"),
        root,
        archive_api_base_url="http://127.0.0.1:1453",
        archive_release_id="release-1",
    )
    assert cases[0].persisted_archive_context.startswith('{"chain:horizon_signal"')
    assert cases[0].persisted_archive_metadata["release_id"] == "release-1"
    assert cases[0].persisted_archive_metadata["source_snapshot_hash"] == "snapshot-1"
    assert provenance["archive_artifacts"][0]["current"]["artifact_path"].endswith("/release-1/effective")
    assert requests and requests[0][0].endswith("/release-1/effective")


def test_cli_fresh_run_explicitly_skips_without_persisted_archive(tmp_path: Path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "fresh.json"
    completed = subprocess.run(
        [sys.executable, "scripts/developer_tools/run_archive_ab_benchmark.py", "--dry-run", "--output", str(output)],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["manifest"]["cases"]
    assert all(item["skipped"] and item["skip_reason"] == "missing_persisted_archive_artifact" for item in payload["manifest"]["cases"])
    assert "missing_persisted_archive_artifact" in completed.stdout


def test_hard_error_bypasses_judge_and_loses_only_invalid_arm():
    case = make_case()
    pair = type("Pair", (), {})()
    pair.case, pair.skipped = case, False
    pair.candidate_a = type("Candidate", (), {"translations": {"source-1:0": "bad"}, "usage": Usage()})()
    pair.candidate_b = type("Candidate", (), {"translations": {entry.source_id: f"译 {entry.text}" for entry in case.source_entries}, "usage": Usage()})()
    result = blind_judge(case, pair, ContentJudge())
    assert result.winner == "B"
    assert "missing_source_id" in result.error_tags


def test_case_level_score_does_not_weight_long_chain_by_string_count():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge())
    result = result.__class__(
        **{**result.__dict__, "error_tags_by_arm": {"A": ("missing_story_context",), "B": ()}}
    )
    score = summarize([result], {"case-1": "event_chain"}, archive_generation=Usage(cost_usd=0.03))
    assert score["unit_of_vote"] == "event_chain_case_or_reference_batch_case"
    assert score["usage"]["avoided_major_context_errors"] == 1
    assert score["usage"]["experiment_total_cost_usd"] == 0.054
    assert score["usage"]["cost_per_avoided_major_error_usd"] == 0.03


def test_review_payload_is_blind_until_reveal_and_store_is_append_only(tmp_path: Path):
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge())
    blind = build_review_payload(pair, result, "manifest-1")
    assert not blind["revealed"] and "reveal" not in blind
    assert "actual_order" not in blind and "llm_winner" not in blind
    assert blind["anonymous_labels"] == ["left", "right"]
    record = make_review_record(blind, reviewer="local", selection="left", anonymous_order=result.presentation_orders[0], confidence=0.8, note="链级判断")
    revealed = reveal_review_payload(blind, record, result)
    assert revealed["reveal"]["llm_winner"] == "A"
    from scripts.developer_tools.archive_ab_review_queue import AppendOnlyReviewStore
    store = AppendOnlyReviewStore(tmp_path / "reviews.jsonl")
    store.append(record)
    store.append(make_reveal_record(record))
    assert len(store.records()) == 2 and not store.records()[0].revealed and store.records()[1].revealed
    summary = review_summary(store.records(), {"case-1": result})
    assert summary["reviewed_case_count"] == 1
    assert summary["record_count"] == 1


def test_review_sampling_is_unique_and_developer_flag_defaults_closed():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge())
    assert sample_case_ids([pair, pair], [result, result], limit=5) == ["case-1"]
    assert not developer_review_enabled({})
    assert developer_review_enabled({"REMIS_ENABLE_ARCHIVE_AB_REVIEW": "1"})


def test_review_summary_excludes_skip_and_uncertain_from_agreement_denominator(tmp_path: Path):
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge())
    blind = build_review_payload(pair, result, "manifest-1")
    records = [
        make_review_record(blind, reviewer="local", selection="skip", anonymous_order=result.presentation_orders[0]),
        make_review_record(blind, reviewer="local", selection="uncertain", anonymous_order=result.presentation_orders[0]),
    ]
    summary = review_summary(records, {"case-1": result})
    assert summary["record_count"] == 1
    assert summary["selection_counts"]["uncertain"] == 1
    assert summary["human_llm_agreement_rate"] is None


def test_scorer_bootstraps_canonical_cluster_once():
    provider = FakeProvider()
    recipe = Recipe("fake", "fake-luna", "low", "archive-ab-prompt-v1")
    pair = translate_pair(make_case(), recipe, Scenario("initial", "fresh"), provider)
    result = blind_judge(pair.case, pair, ContentJudge())
    score = summarize(
        [result, result],
        {"case-1": "event_chain"},
        case_cluster_by_id={"case-1": "chain-1"},
    )
    assert score["overall"]["case_count"] == 1


def test_real_corpus_manifest_expands_whole_chain_and_reference_batch():
    root = Path(r"J:\remis-aventine-benchmark-corpus")
    if not root.exists():
        return
    cases, provenance = load_cases(Path("tests/fixtures/remis_archive_ab_v1/cases.json"), root)
    by_id = {case.case_id: case for case in cases}
    assert len(by_id["horizon_signal__chain"].source_entries) > 20
    assert len(by_id["toxic_god__first_quest_sinople"].source_entries) > 20
    assert by_id["horizon_signal__technology_reference_batch"].case_kind == "reference_batch"
    assert "Horizon Signal is a rare" in by_id["horizon_signal__chain"].wiki_context
    assert "eight numbered quests" in by_id["toxic_god__first_quest_sinople"].wiki_context
    assert provenance["wiki_package"]["schema_version"] == "remis-archive-ab-wiki-evidence-v2"
    assert all(item["sha256"] for item in provenance["source_files"] + provenance["gold_files"])
