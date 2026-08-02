import sqlite3
from types import SimpleNamespace

import pytest

from scripts.core.services.context_candidate_adapter import ContextCandidateAdapter
from scripts.core.services.context_source_parser import ContextSourceParser


class FakeCandidateStore:
    def __init__(self):
        self.items = []

    def load_candidates(self, project_id):
        return [item for item in self.items if item.project_id == project_id]

    def save_candidates(self, project_id, candidates):
        self.items = [item for item in candidates if item.project_id == project_id]


class FakeReviewMiner:
    def __init__(self, fail_on_call=None):
        self.calls = 0
        self.fail_on_call = fail_on_call

    def review_terms(self, candidates, **kwargs):
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise TimeoutError("review unavailable")
        return {
            item["original"]: SimpleNamespace(
                suggestion=f"译-{item['original']}", reasoning="review fallback", confidence=0.8
            )
            for item in candidates
        }


def _parsed(tmp_path, count=1):
    root = tmp_path / "mod"
    path = root / "localisation" / "main.yml"
    path.parent.mkdir(parents=True)
    values = "\n".join(f" key_{i}:0 \"Term {i}\"" for i in range(count))
    path.write_text(f"l_english:\n{values}\n", encoding="utf-8")
    return root, ContextSourceParser().parse_files([str(path)], str(root))


def _term(item, original=None, direct=False):
    payload = {
        "original": original or item.source_text,
        "category": "concept",
        "confidence": 0.9,
        "evidence": [{
            "source_item_id": item.source_item_id,
            "snippet": item.source_text,
            "relative_path": item.relative_path,
            "item_key": item.item_key,
            "source_order": item.source_order,
        }],
    }
    if direct:
        payload.update({"suggestion": "直接译文", "reasoning": "extraction evidence"})
    return payload


def test_extraction_payload_preserves_direct_fields_and_stable_source_mapping(tmp_path):
    _, parsed = _parsed(tmp_path)
    item = parsed[0].items[0]
    candidate_store = FakeCandidateStore()
    adapter = ContextCandidateAdapter(candidate_store)
    from scripts.core.db_migrations import migrate_main_database
    from scripts.core.repositories.context_analysis_batch_repository import ContextAnalysisBatchRepository

    db_path = tmp_path / "analysis.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """INSERT INTO projects
               (project_id, name, game_id, source_path, source_language, status)
               VALUES ('project-1', 'Context Mod', 'vic3', '/source', 'english', 'active')"""
        )
    extraction = SimpleNamespace(terms=[_term(item, direct=True)])
    batch_store = ContextAnalysisBatchRepository(str(db_path))

    result = adapter.process_terms(
        "project-1", parsed, [extraction], FakeReviewMiner(), {}, "en", "zh-CN", "Vic3", "en",
        batch_store=batch_store,
    )
    saved = batch_store.get_batch(result["run_id"], "extraction", 0)

    assert result["new_terms"] == 1
    assert candidate_store.items[0].suggestion == "直接译文"
    term = saved.payload["terms"][0]
    assert term["suggestion"] == "直接译文"
    assert term["reasoning"] == "extraction evidence"
    assert term["source_references"] == [{
        "source_item_id": item.source_item_id,
        "relative_path": item.relative_path,
        "item_key": item.item_key,
        "source_order": item.source_order,
    }]
    restored = adapter.rebuild_source_items(saved.payload)
    assert [(source.source_item_id, source.relative_path, source.item_key, source.source_order, source.source_text)
            for source in restored] == [
        (item.source_item_id, item.relative_path, item.item_key, item.source_order, item.source_text)
    ]


def test_review_failure_retains_previous_review_batch_and_retry_reuses_it(tmp_path):
    _, parsed = _parsed(tmp_path, count=21)
    terms = [_term(item, original=f"Term {i}") for i, item in enumerate(parsed[0].items)]
    extraction = SimpleNamespace(terms=terms)
    candidate_store = FakeCandidateStore()
    from scripts.core.db_migrations import migrate_main_database
    from scripts.core.repositories.context_analysis_batch_repository import ContextAnalysisBatchRepository

    db_path = tmp_path / "analysis.sqlite"
    migrate_main_database(str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """INSERT INTO projects
               (project_id, name, game_id, source_path, source_language, status)
               VALUES ('project-1', 'Context Mod', 'vic3', '/source', 'english', 'active')"""
        )
    batch_store = ContextAnalysisBatchRepository(str(db_path))
    adapter = ContextCandidateAdapter(candidate_store, batch_store)

    with pytest.raises(TimeoutError):
        adapter.process_terms(
            "project-1", parsed, [extraction], FakeReviewMiner(fail_on_call=2), {},
            "en", "zh-CN", "Vic3", "en", task_id="task-1",
        )
    failed_run = next(
        run for run_id in {
            row[0] for row in sqlite3.connect(db_path).execute(
                "SELECT run_id FROM context_analysis_runs"
            ).fetchall()
        }
        if (run := batch_store.get_run(run_id)) and run.status == "failed"
    )
    assert batch_store.get_batch(failed_run.run_id, "review", 0).status == "succeeded"
    assert batch_store.get_batch(failed_run.run_id, "review", 1).status == "failed"

    result = adapter.process_terms(
        "project-1", parsed, [extraction], FakeReviewMiner(), {},
        "en", "zh-CN", "Vic3", "en", task_id="task-2",
    )
    assert result["run_id"] == failed_run.run_id
    assert len(batch_store.list_batches(failed_run.run_id, "review")) == 2
