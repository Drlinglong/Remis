import sqlite3

import pytest

from scripts.core.db_migrations import MAIN_DB_TARGET_VERSION, migrate_main_database
from scripts.core.repositories.context_archive_repository import (
    ContextArchiveBusyError,
    ContextArchiveRepository,
)


def _database(tmp_path, *, run_status="complete"):
    db_path = tmp_path / "archive-removal.sqlite"
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        for project_id, name in (("project-1", "Horizon"), ("project-2", "Keep")):
            connection.execute(
                "INSERT INTO projects "
                "(project_id, name, game_id, source_path, source_language, status) "
                "VALUES (?, ?, 'stellaris', '/source', 'en', 'active')",
                (project_id, name),
            )
        connection.execute(
            "INSERT INTO context_source_items VALUES "
            "('source-1', 'project-1', 'localization', 'events.yml::akx.1', "
            "'Signal', 'hash-1', '{}', '2026-08-03T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO context_contributions VALUES "
            "('contribution-1', 'source-1', 'event', 'signal', '{}', "
            "'text_inferred', '2026-08-03T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO context_aggregates VALUES "
            "('aggregate-1', 'project-1', 'event', 'signal', '{}', '2026-08-03T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO context_aggregate_contributions VALUES "
            "('aggregate-1', 'contribution-1')"
        )
        for project_id, release_id in (("project-1", "release-1"), ("project-2", "release-2")):
            connection.execute(
                "INSERT INTO context_releases "
                "(release_id, project_id, source_snapshot_hash, analysis_scope_json, "
                "schema_version, prompt_version, provider_id, model_id, "
                "analysis_config_json, created_at) "
                "VALUES (?, ?, 'snapshot', '{}', 'context-v1', 'prompt-v1', "
                "'local', 'model', '{}', '2026-08-03T00:00:00Z')",
                (release_id, project_id),
            )
        connection.execute(
            "INSERT INTO context_release_aggregates VALUES "
            "('release-1', 'aggregate-1', 'event', 'signal', '{}', '[\"contribution-1\"]')"
        )
        connection.execute(
            "INSERT INTO context_release_syntheses VALUES "
            "('synthesis-1', 'release-1', 'aggregate-1', 'event:signal', '{}')"
        )
        connection.execute(
            "INSERT INTO context_release_delivery_memberships VALUES "
            "('release-1', 'aggregate-1', 'source-1', 'primary_member', 1.0, "
            "'text_inferred', NULL)"
        )
        connection.execute(
            "INSERT INTO context_release_overrides VALUES "
            "('release-1', 'event:signal', '{}', 'human note')"
        )
        connection.execute(
            "INSERT INTO context_drafts VALUES "
            "('draft-1', 'project-1', 'release-1', 'draft', "
            "'2026-08-03T00:00:00Z', '2026-08-03T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO context_draft_overrides VALUES "
            "('draft-1', 'event:signal', '{}', NULL, '2026-08-03T00:00:00Z')"
        )
        connection.execute(
            "INSERT INTO context_analysis_runs VALUES "
            "('run-1', 'task-1', 'project-1', 'snapshot', '{}', 'config', '{}', "
            "'aggregation', ?, 'not_published', '2026-08-03T00:00:00Z', "
            "'2026-08-03T00:00:00Z', NULL)",
            (run_status,),
        )
        connection.execute(
            "INSERT INTO context_analysis_batches VALUES "
            "('batch-1', 'run-1', 'aggregation', 0, '[]', '{}', 'succeeded', NULL, "
            "'2026-08-03T00:00:00Z', '2026-08-03T00:00:00Z')"
        )
    return ContextArchiveRepository(str(db_path)), db_path


def test_project_archive_removal_is_scoped_and_restores_immutable_guards(tmp_path):
    repository, db_path = _database(tmp_path)

    result = repository.remove_project_archive("project-1")

    assert result["removed"] is True
    assert result["counts"] == {
        "releases": 1,
        "drafts": 1,
        "source_items": 1,
        "contributions": 1,
        "aggregates": 1,
        "syntheses": 1,
        "delivery_memberships": 1,
        "analysis_runs": 1,
        "analysis_batches": 1,
        "aggregate_links": 1,
    }
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM projects WHERE project_id = 'project-1'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM context_releases WHERE project_id = 'project-1'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM context_releases WHERE project_id = 'project-2'"
        ).fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM context_releases WHERE release_id = 'release-2'")


def test_project_archive_removal_refuses_an_active_analysis(tmp_path):
    repository, _ = _database(tmp_path, run_status="running")

    with pytest.raises(ContextArchiveBusyError, match="still active"):
        repository.remove_project_archive("project-1")

    assert repository.archive_counts("project-1")["releases"] == 1
