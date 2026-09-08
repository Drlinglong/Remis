"""Run a deterministic, no-provider smoke evaluation of the archive A/B contract."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.developer_tools.archive_ab_contract import Recipe, Scenario, Usage, canonical_json, sha256_text
from scripts.developer_tools.archive_ab_fixtures import load_cases
from scripts.developer_tools.archive_ab_review_queue import build_review_payload
from scripts.developer_tools.archive_ab_runner import (
    blind_judge,
    build_run_manifest,
    semantic_identity_by_arm,
    translate_pair,
)
from scripts.developer_tools.archive_ab_scorer import summarize


class DryRunProvider:
    """A transparent fake: it returns source text with a marker and no network."""

    def translate(self, prompt: str, *, case_id: str, request_id: str):
        entries = {}
        current_id = None
        current_lines: list[str] = []

        def flush() -> None:
            if current_id is not None:
                entries[current_id] = "dry-run: " + "\n".join(current_lines)

        for line in prompt.splitlines():
            if line.startswith("Archive context"):
                break
            if line.startswith("- ") and ": " in line:
                flush()
                source_id, text = line[2:].split(": ", 1)
                current_id = source_id
                current_lines = [text]
                continue
            if current_id is not None:
                current_lines.append(line)
        flush()
        return entries, Usage(input_tokens=len(prompt.split()), output_tokens=sum(len(text.split()) for text in entries.values()))


class DryRunJudge:
    def judge(self, prompt: str):
        payload = {
            "winner": "tie",
            "confidence": 0.0,
            "error_tags": [],
            "evidence": ["dry-run: no quality judgment requested"],
            "candidate_error_tags": {"A": [], "B": []},
        }
        return payload, Usage(input_tokens=len(prompt.split()), output_tokens=len(canonical_json(payload).split()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-root", type=Path, default=Path(r"J:\remis-aventine-benchmark-corpus"))
    parser.add_argument("--fixture", type=Path, default=Path("tests/fixtures/remis_archive_ab_v1/cases.json"))
    parser.add_argument("--output", type=Path, default=Path(".tmp/archive-ab/dry-run.json"))
    parser.add_argument("--mode", choices=("initial", "incremental"), default="initial")
    parser.add_argument("--archive-mode", choices=("none", "fresh", "stale"), default="fresh")
    parser.add_argument("--archive-api-base-url", default=None, help="localhost Remis API base URL for published archive releases")
    parser.add_argument("--archive-release-id", default=None, help="published Remis release used by the fresh archive arm")
    parser.add_argument("--archive-previous-release-id", default=None, help="published Remis release used by the stale archive arm")
    parser.add_argument("--changed-source-id", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true", help="required safety acknowledgement; no real provider exists in this tool")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        raise SystemExit("Only --dry-run is implemented; real paid translation/judging requires separate authorization and integration review.")
    cases, provenance = load_cases(
        args.fixture,
        args.corpus_root,
        archive_api_base_url=args.archive_api_base_url,
        archive_release_id=args.archive_release_id,
        archive_previous_release_id=args.archive_previous_release_id,
    )
    recipe = Recipe(
        "fake", "offline-dry-run", "low", "archive-ab-prompt-v3",
        provider_revision="offline-dry-run-v1", temperature=0.0, top_p=1.0, seed=198,
    )
    scenario = Scenario(args.mode, args.archive_mode, frozenset(args.changed_source_id))
    provider = DryRunProvider()
    judge = DryRunJudge()
    pairs = [translate_pair(case, recipe, scenario, provider) for case in cases]
    results = [blind_judge(pair.case, pair, judge) for pair in pairs if not pair.skipped]
    manifest = build_run_manifest(pairs, results, recipe, scenario, **provenance)
    score = summarize(
        results,
        {case.case_id: case.case_kind for case in cases},
        case_cluster_by_id={case.case_id: case.chain_id or case.reference_batch_id or case.case_id for case in cases},
    )
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    run_hash = sha256_text(canonical_json({"manifest": manifest, "score": score}))[:16]
    run_id = f"{created_at.replace(':', '').replace('+00:00', 'Z')}-{run_hash}"
    manifest["created_at"] = created_at
    manifest["run_id"] = run_id
    manifest["manifest_id"] = run_id
    results_by_id = {result.case_id: result for result in results}
    review_cases = []
    for pair in pairs:
        result = results_by_id.get(pair.case.case_id)
        if result is None:
            continue
        blind = build_review_payload(pair, result, manifest["manifest_id"])
        review_cases.append({
            "blind": blind,
            "private": {
                "presentation_order": list(result.presentation_orders[0]),
                "winner": result.winner,
                "confidence": result.confidence,
                "error_tags": list(result.error_tags),
                "error_tags_by_arm": {arm: list(tags) for arm, tags in result.error_tags_by_arm.items()},
                "evidence": list(result.evidence),
                "semantic_identity_by_arm": semantic_identity_by_arm(scenario),
                "candidate_by_arm": {
                    "A": dict(pair.candidate_a.translations),
                    "B": dict(pair.candidate_b.translations),
                },
            },
        })
    payload = {"manifest": manifest, "score": score, "review_cases": review_cases}
    output = args.output
    if output == Path(".tmp/archive-ab/dry-run.json"):
        output = output.parent / f"{output.stem}-{run_id}.json"
    if output.exists():
        raise SystemExit(f"Refusing to overwrite immutable benchmark output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(serialized, encoding="utf-8", newline="\n")
        os.rename(temporary, output)
    except FileExistsError as exc:
        raise SystemExit(f"Refusing to overwrite immutable benchmark output: {output}") from exc
    finally:
        if temporary.exists():
            temporary.unlink()
    skipped = [pair for pair in pairs if pair.skipped]
    print(json.dumps({
        "output": str(output), "run_id": run_id, "case_count": len(results), "skipped_count": len(skipped),
        "skip_reasons": sorted({pair.skip_reason for pair in skipped}),
        "mode": args.mode, "archive_mode": args.archive_mode,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
