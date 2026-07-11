"""Run the neologism miner against the repository's Stellaris golden sample."""

import argparse
import json
import time
from pathlib import Path
from typing import Iterable

from scripts.app_settings import PROJECT_ROOT
from scripts.core.api_handler import get_handler
from scripts.core.file_parser import extract_translatable_content
from scripts.core.neologism_manager import NeologismManager
from scripts.core.neologism_miner import NeologismMiner


def normalize_term(term: str) -> str:
    return " ".join((term or "").casefold().split())


def score_predictions(predictions: Iterable[str], expected: Iterable[str], source_text: str) -> dict:
    prediction_map = {normalize_term(term): term for term in predictions}
    expected_map = {normalize_term(term): term for term in expected}
    hits = sorted(expected_map[key] for key in expected_map.keys() & prediction_map.keys())
    missing = sorted(expected_map[key] for key in expected_map.keys() - prediction_map.keys())
    source_normalized = source_text.casefold()
    ungrounded = sorted(term for term in prediction_map.values() if term.casefold() not in source_normalized)
    recall = len(hits) / len(expected_map) if expected_map else 1.0
    grounding_rate = (
        (len(prediction_map) - len(ungrounded)) / len(prediction_map)
        if prediction_map
        else 1.0
    )
    return {
        "candidate_count": len(prediction_map),
        "expected_count": len(expected_map),
        "hits": hits,
        "missing": missing,
        "ungrounded": ungrounded,
        "recall": round(recall, 4),
        "grounding_rate": round(grounding_rate, 4),
    }


def run_eval(provider: str, model_name: str | None, fixture_path: Path) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    source_path = Path(PROJECT_ROOT) / fixture["source_file"]
    _, texts, _ = extract_translatable_content(str(source_path))
    handler = get_handler(provider, model_name=model_name)
    miner = NeologismMiner(handler)

    started = time.perf_counter()
    predictions = []
    for chunk in NeologismManager._chunk_texts(texts):
        predictions.extend(term.original for term in miner.extract_terms(
            chunk,
            game_name=fixture["game_name"],
        ))
    elapsed_seconds = time.perf_counter() - started

    result = score_predictions(predictions, fixture["expected_terms"], "\n".join(texts))
    result.update({
        "fixture": fixture["name"],
        "provider": provider,
        "model": model_name,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "passed": (
            result["recall"] >= fixture["minimum_recall"]
            and result["grounding_rate"] >= fixture["minimum_grounding_rate"]
        ),
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default="gemini")
    parser.add_argument("--model")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path(PROJECT_ROOT) / "tests" / "fixtures" / "neologism_eval_stellaris.json",
    )
    args = parser.parse_args()
    result = run_eval(args.provider, args.model, args.fixture)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
