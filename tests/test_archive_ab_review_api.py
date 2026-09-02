from __future__ import annotations

import json
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

from scripts.developer_tools import archive_ab_review_adapter as adapter
from scripts.developer_tools.run_archive_ab_benchmark import main as run_benchmark
from scripts.routers import archive_ab_review as review_router


def _result_payload() -> dict:
    blind = {
        "case_id": "chain-1",
        "manifest_id": "run-1",
        "dataset_id": "stellaris:horizon-signal",
        "case_kind": "event_chain",
        "chain_id": "horizon_signal",
        "reference_batch_id": None,
        "chunk": {"index": 0, "count": 1, "reason": "not_chunked"},
        "source_entries": [{"source_id": "event.1", "text": "The signal returns."}],
        "gold_facts": ["The signal returns through a loop."],
        "wiki_evidence_ids": ["paradox-horizon-signal"],
        "anonymous_candidates": [{"event.1": "左译文"}, {"event.1": "右译文"}],
        "anonymous_labels": ["left", "right"],
        "revealed": False,
    }
    return {
        "manifest": {"manifest_id": "run-1", "schema_version": "remis-archive-ab-run-v1", "cases": [{}]},
        "score": {"unit_of_vote": "event_chain_case_or_reference_batch_case"},
        "review_cases": [{
            "blind": blind,
            "private": {
                "presentation_order": ["B", "A"],
                "winner": "A",
                "error_tags": [],
                "evidence": ["left preserves the loop."],
                "semantic_identity_by_arm": {
                    "A": {"label": "baseline(no archive)", "role": "baseline", "archive_mode": "none"},
                    "B": {"label": "archive(fresh)", "role": "archive", "archive_mode": "fresh"},
                },
            },
        }],
    }


def _client(tmp_path: Path, monkeypatch):
    output_root = tmp_path / "archive-ab"
    output_root.mkdir()
    (output_root / "run-1.json").write_text(json.dumps(_result_payload(), ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(adapter, "ARCHIVE_AB_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(adapter, "REVIEW_QUEUE_PATH", output_root / "review-queue.jsonl")
    monkeypatch.setattr(review_router, "archive_ab_review_enabled", lambda: True)
    app = FastAPI()
    app.include_router(review_router.router)
    return TestClient(app)


def test_disabled_endpoint_is_closed(monkeypatch):
    monkeypatch.setattr(review_router, "archive_ab_review_enabled", lambda: False)
    app = FastAPI()
    app.include_router(review_router.router)
    with TestClient(app) as client:
        assert client.get("/api/archive-ab-review/status").json()["enabled"] is False
        assert client.get("/api/archive-ab-review/cases").status_code == 404


def test_cases_are_blind_until_append_only_submit_then_reveal(tmp_path: Path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        response = client.get("/api/archive-ab-review/cases", params={"status": "unreviewed"})
        assert response.status_code == 200
        case = response.json()["cases"][0]
        assert [item["anonymous_label"] for item in case["anonymous_outputs"]] == ["left", "right"]
        assert "reveal" not in case
        assert "candidate_by_arm" not in response.text
        assert "judgments" not in response.text
        assert "arm_randomization" not in response.text
        assert "score" not in response.json()

        submitted = client.post("/api/archive-ab-review/reviews", json={
            "manifest_id": "run-1",
            "case_id": "chain-1",
            "selection": "left",
            "error_tags": ["missing_story_context"],
            "confidence": 0.8,
            "note": "整链判断",
        })
        assert submitted.status_code == 200, submitted.text
        revealed = submitted.json()["case"]
        assert revealed["revealed"] is True
        assert revealed["reveal"]["llm_winner"] == "A"
        assert revealed["reveal"]["semantic_identity"] == {
            "left": {"arm": "B", "label": "archive(fresh)", "role": "archive", "archive_mode": "fresh"},
            "right": {"arm": "A", "label": "baseline(no archive)", "role": "baseline", "archive_mode": "none"},
        }
        summary = client.get("/api/archive-ab-review/summary", params={"manifest_id": "run-1"})
        assert summary.json()["reviewed_case_count"] == 1
        assert summary.json()["record_count"] == 1
        assert len((tmp_path / "archive-ab" / "review-queue.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_review_filters_and_history_do_not_expose_arm_order(tmp_path: Path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        assert client.get("/api/archive-ab-review/cases", params={"dataset_id": "missing"}).json()["cases"] == []
        client.post("/api/archive-ab-review/reviews", json={
            "manifest_id": "run-1", "case_id": "chain-1", "selection": "skip", "confidence": 0,
        })
        history = client.get("/api/archive-ab-review/reviews").json()["records"]
        assert history[-1]["selection"] == "skip"
        assert "anonymous_order" not in history[-1]


def test_api_contract_reads_real_runner_review_artifact(tmp_path: Path, monkeypatch):
    output_root = tmp_path / "archive-ab"
    output_root.mkdir()
    output = output_root / "runner.json"
    monkeypatch.setattr(sys, "argv", [
        "run_archive_ab_benchmark.py", "--dry-run", "--archive-mode", "none", "--output", str(output),
    ])
    assert run_benchmark() == 0
    monkeypatch.setattr(adapter, "ARCHIVE_AB_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(adapter, "REVIEW_QUEUE_PATH", output_root / "review-queue.jsonl")
    monkeypatch.setattr(review_router, "archive_ab_review_enabled", lambda: True)
    app = FastAPI()
    app.include_router(review_router.router)
    with TestClient(app) as client:
        response = client.get("/api/archive-ab-review/cases", params={"status": "unreviewed"})
        assert response.status_code == 200
        assert response.json()["total_count"] == 3
        assert response.json()["cases"][0]["dataset_id"].startswith("stellaris:")
        assert "judgments" not in response.text
