import sqlite3

import pytest

from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.context_analysis_batch_repository import (
    ContextAnalysisBatchConflictError,
    ContextAnalysisBatchRepository,
    ContextAnalysisConfigurationError,
)


def _repository(tmp_path):
    db_path = tmp_path / "analysis.sqlite"
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """INSERT INTO projects
               (project_id, name, game_id, source_path, source_language, status)
               VALUES ('project-1', 'Context Mod', 'vic3', '/source', 'english', 'active')"""
        )
    return ContextAnalysisBatchRepository(str(db_path)), db_path


def test_migration_creates_formal_analysis_tables(tmp_path):
    _, db_path = _repository(tmp_path)
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"context_analysis_runs", "context_analysis_batches"} <= tables


def test_run_resume_requires_exact_snapshot_scope_and_config(tmp_path):
    repository, _ = _repository(tmp_path)
    first = repository.start_or_resume_run(
        "project-1", "task-1", "snapshot-a", {"mode": "terms_only"}, {"model": "local"}
    )
    same = repository.start_or_resume_run(
        "project-1", "task-2", "snapshot-a", {"mode": "terms_only"}, {"model": "local"}
    )
    changed_snapshot = repository.start_or_resume_run(
        "project-1", "task-3", "snapshot-b", {"mode": "terms_only"}, {"model": "local"}
    )
    changed_config = repository.start_or_resume_run(
        "project-1", "task-4", "snapshot-a", {"mode": "terms_only"}, {"model": "remote"}
    )
    changed_scope = repository.start_or_resume_run(
        "project-1", "task-5", "snapshot-a", {"mode": "narrative_context"}, {"model": "local"}
    )

    assert same.run_id == first.run_id
    assert changed_snapshot.run_id != first.run_id
    assert changed_config.run_id != first.run_id
    assert changed_scope.run_id != first.run_id


def test_successful_batch_is_idempotent_and_immutable(tmp_path):
    repository, _ = _repository(tmp_path)
    run = repository.start_or_resume_run("project-1", "task-1", "snapshot-a", {"mode": "terms_only"})
    saved = repository.save_batch(run.run_id, "extraction", 0, ["source-1"], {"terms": []})
    repeated = repository.save_batch(run.run_id, "extraction", 0, ["source-1"], {"terms": []})

    assert repeated.batch_id == saved.batch_id
    assert len(repository.list_batches(run.run_id, "extraction")) == 1
    with pytest.raises(ContextAnalysisBatchConflictError):
        repository.save_batch(run.run_id, "extraction", 0, ["source-2"], {"terms": []})


def test_global_aggregation_is_a_first_class_resumable_phase(tmp_path):
    repository, _ = _repository(tmp_path)
    run = repository.start_or_resume_run(
        "project-1", "task-1", "snapshot-a", {"mode": "narrative_context"}
    )

    saved = repository.save_batch(
        run.run_id,
        "aggregation",
        0,
        ["source-1", "source-2"],
        {"extraction": {"events": [], "delivery_assignments": []}},
    )

    assert saved.phase == "aggregation"
    assert repository.get_run(run.run_id).phase == "aggregation"
    assert repository.resume_checkpoint(run.run_id)["last_successful_batch"]["aggregation"] == 0


def test_synthesis_is_a_first_class_resumable_phase(tmp_path):
    repository, _ = _repository(tmp_path)
    run = repository.start_or_resume_run(
        "project-1", "task-1", "snapshot-a", {"mode": "narrative_context"}
    )

    saved = repository.save_batch(
        run.run_id,
        "synthesis",
        0,
        ["source-1"],
        {"syntheses": [{"synthesis_id": "synthesis-1"}]},
    )

    assert saved.phase == "synthesis"
    assert repository.get_run(run.run_id).phase == "synthesis"
    assert repository.resume_checkpoint(run.run_id)["last_successful_batch"]["synthesis"] == 0


def test_failed_review_keeps_previous_success_and_can_resume(tmp_path):
    repository, _ = _repository(tmp_path)
    run = repository.start_or_resume_run("project-1", "task-1", "snapshot-a", {"mode": "terms_only"})
    repository.save_batch(run.run_id, "extraction", 0, ["source-1"], {"terms": [{"original": "Republic"}]})
    repository.save_batch(run.run_id, "review", 0, ["source-1"], {"reviews": {"Republic": {"suggestion": "共和国"}}})
    failed = repository.save_batch(
        run.run_id, "review", 1, ["source-2"], {"reviews": {}}, status="failed",
        error={"type": "TimeoutError", "message": "review unavailable"},
    )
    checkpoint = repository.resume_checkpoint(run.run_id)

    assert failed.status == "failed"
    assert checkpoint["last_successful_batch"] == {"extraction": 0, "review": 0}
    assert repository.get_batch(run.run_id, "review", 0).payload["reviews"]["Republic"]["suggestion"] == "共和国"

    retried = repository.save_batch(run.run_id, "review", 1, ["source-2"], {"reviews": {"Consul": {}}})
    assert retried.status == "succeeded"
    assert repository.resume_checkpoint(run.run_id)["last_successful_batch"]["review"] == 1


def test_credentials_are_rejected_from_persisted_analysis_config(tmp_path):
    repository, _ = _repository(tmp_path)
    with pytest.raises(ContextAnalysisConfigurationError):
        repository.start_or_resume_run(
            "project-1", "task-1", "snapshot-a", {"mode": "terms_only"}, {"provider": {"api_key": "redacted"}}
        )


def test_publication_flag_is_separate_from_batch_checkpoint(tmp_path):
    repository, _ = _repository(tmp_path)
    run = repository.start_or_resume_run("project-1", "task-1", "snapshot-a", {"mode": "terms_only"})
    repository.save_batch(run.run_id, "extraction", 0, ["source-1"], {"terms": []})
    complete = repository.mark_analysis_ready(run.run_id)
    published = repository.mark_published(run.run_id, ["candidate-1"])

    assert complete.publication_status == "not_published"
    assert complete.phase == "publishing"
    assert complete.status == "running"
    assert published.status == "complete"
    assert published.publication_status == "published"
    assert len(repository.list_batches(run.run_id)) == 1
