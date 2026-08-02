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
        self.last_candidates = []

    def review_terms(self, candidates, **kwargs):
        self.calls += 1
        self.last_candidates = list(candidates)
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


def test_direct_extraction_fields_skip_review_and_preserve_candidate_source(tmp_path):
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
    assert result["new_terms"] == 1
    assert candidate_store.items[0].suggestion == "直接译文"
    assert candidate_store.items[0].reasoning == "extraction evidence"
    assert candidate_store.items[0].source_file == item.relative_path


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


def test_conflicting_direct_suggestions_trigger_one_review_and_use_its_decision(tmp_path):
    _, parsed = _parsed(tmp_path)
    item = parsed[0].items[0]
    first = _term(item, direct=True)
    second = _term(item, direct=True)
    first.update({"suggestion": "术语甲", "reasoning": "first batch"})
    second.update({"suggestion": "术语乙", "reasoning": "second batch"})
    store = FakeCandidateStore()
    miner = FakeReviewMiner()

    result = ContextCandidateAdapter(store).process_terms(
        "project-1",
        parsed,
        [SimpleNamespace(terms=[first]), SimpleNamespace(terms=[second])],
        miner,
        {},
        "en",
        "zh-CN",
        "Vic3",
        "zh-CN",
    )

    assert result["new_terms"] == 1
    assert miner.calls == 1
    assert miner.last_candidates[0]["source_references"][0]["item_key"] == "key_0:0"
    assert store.items[0].suggestion == "译-Term 0"
    assert store.items[0].reasoning == "review fallback"
