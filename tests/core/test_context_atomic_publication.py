from __future__ import annotations

import sqlite3

import pytest

from scripts.core.db_migrations import (
    MAIN_DB_MIGRATIONS,
    MAIN_DB_TARGET_VERSION,
    migrate_main_database,
)
from scripts.core.repositories.context_analysis_batch_repository import (
    ContextAnalysisBatchRepository,
)
from scripts.core.repositories.context_publication_repository import (
    ContextPublicationRepository,
)
from scripts.core.repositories.context_repository import ContextRepository
from scripts.schemas.context import (
    ContextAggregate,
    ContextContribution,
    ContextReleaseMetadata,
    ContextSourceItem,
    GeneratedSynthesis,
)


def _setup(tmp_path):
    db_path = tmp_path / "atomic-publication.sqlite"
    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES ('project-1', 'Atomic Context', 'vic3', '/source', 'english', 'active')
            """
        )
    repository = ContextRepository(str(db_path))
    repository.create_source_item(
        ContextSourceItem(
            source_item_id="source-1",
            project_id="project-1",
            source_type="localization",
            source_ref="events/republic.yml::republic.1",
            content="The Republic appoints a consul.",
            content_hash="hash-source-1",
        )
    )
    repository.create_contribution(
        ContextContribution(
            contribution_id="contribution-1",
            source_item_id="source-1",
            contribution_type="fact",
            subject_key="republic",
            payload={"office": "consul"},
            provenance="text_inferred",
        )
    )
    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-republic",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="republic",
            payload={"name": "Republic"},
            contribution_ids=["contribution-1"],
        )
    )
    run = ContextAnalysisBatchRepository(str(db_path)).start_or_resume_run(
        "project-1",
        "task-1",
        "snapshot-1",
        {"mode": "narrative_context"},
        {"model": "local"},
    )
    draft = repository.create_draft("project-1")
    metadata = ContextReleaseMetadata(
        source_snapshot_hash="snapshot-1",
        analysis_scope={"mode": "narrative_context"},
        schema_version="context-v3",
        prompt_version="context-archive-v8",
        provider_id="local",
        model_id="local-model",
    )
    synthesis = GeneratedSynthesis(
        synthesis_id="synthesis-1",
        aggregate_id="aggregate-republic",
        context_key="republic",
        content={"summary": "A republic appoints a consul."},
    )
    return db_path, repository, run, draft, metadata, synthesis


@pytest.mark.parametrize(
    "failure_stage",
    ["after_children_before_run_update", "after_run_update_before_seal"],
)
def test_publish_retry_after_crash_rolls_back_then_returns_existing_release(
    tmp_path, failure_stage
):
    db_path, repository, run, draft, metadata, synthesis = _setup(tmp_path)

    def fail_after_children(stage):
        if stage == failure_stage:
            raise RuntimeError("simulated publication crash")

    crashing = ContextPublicationRepository(
        str(db_path), failure_injector=fail_after_children
    )
    with pytest.raises(RuntimeError, match="simulated publication crash"):
        crashing.publish_draft(
            draft.draft_id,
            metadata,
            ["aggregate-republic"],
            [synthesis],
            analysis_run_id=run.run_id,
        )

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM context_releases").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM context_release_aggregates"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT publication_status FROM context_analysis_runs WHERE run_id = ?",
            (run.run_id,),
        ).fetchone()[0] == "not_published"

    publisher = ContextPublicationRepository(str(db_path))
    release = publisher.publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-republic"],
        [synthesis],
        analysis_run_id=run.run_id,
    )
    repeated = publisher.publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-republic"],
        [synthesis],
        analysis_run_id=run.run_id,
    )

    assert repeated.release_id == release.release_id
    assert repeated.analysis_run_id == run.run_id
    assert repository.get_release(release.release_id).analysis_run_id == run.run_id
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM context_releases WHERE analysis_run_id = ?",
            (run.run_id,),
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT status, publication_status FROM context_analysis_runs WHERE run_id = ?",
            (run.run_id,),
        ).fetchone() == ("complete", "published")


def test_one_run_has_at_most_one_release(tmp_path):
    db_path, _, run, draft, metadata, synthesis = _setup(tmp_path)
    publisher = ContextPublicationRepository(str(db_path))

    first = publisher.publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-republic"],
        [synthesis],
        analysis_run_id=run.run_id,
    )
    second = publisher.publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-republic"],
        [synthesis],
        analysis_run_id=run.run_id,
    )

    assert second.release_id == first.release_id
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM context_releases WHERE analysis_run_id = ?",
            (run.run_id,),
        ).fetchone()[0] == 1


def test_published_release_rejects_new_child_insert(tmp_path):
    db_path, repository, run, draft, metadata, synthesis = _setup(tmp_path)
    release = ContextPublicationRepository(str(db_path)).publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-republic"],
        [synthesis],
        analysis_run_id=run.run_id,
    )
    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-second",
            project_id="project-1",
            aggregate_type="entity",
            aggregate_key="second",
            payload={"name": "Second"},
            contribution_ids=["contribution-1"],
        )
    )

    statements = (
        (
            "INSERT INTO context_release_aggregates "
            "(release_id, aggregate_id, aggregate_type, aggregate_key, payload_json, contribution_ids_json) "
            "VALUES (?, 'aggregate-second', 'entity', 'second', '{}', '[]')",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_syntheses "
            "(synthesis_id, release_id, aggregate_id, context_key, content_json) "
            "VALUES ('synthesis-new', ?, 'aggregate-republic', 'republic', '{}')",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_delivery_memberships "
            "(release_id, aggregate_id, source_item_id, role, confidence, provenance) "
            "VALUES (?, 'aggregate-republic', 'source-1', 'primary_member', 1.0, 'text_inferred')",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_overrides (release_id, target_key, value_json) "
            "VALUES (?, 'new-key', '{}')",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_files "
            "(release_id, relative_path, source_sha256, size) "
            "VALUES (?, 'late.yml', 'sha', 1)",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_source_items "
            "(release_id, source_item_id, source_revision_id, relative_path, "
            "source_ref, content, content_hash) "
            "VALUES (?, 'late-source', 'late-revision', 'late.yml', "
            "'late.yml::late', 'Late', 'hash')",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_local_units "
            "(release_id, local_unit_id, unit_key, unit_order) "
            "VALUES (?, 'late-unit', 'late', 0)",
            (release.release_id,),
        ),
        (
            "INSERT INTO context_release_local_unit_members "
            "(release_id, local_unit_id, source_item_id, member_order) "
            "VALUES (?, 'late-unit', 'late-source', 0)",
            (release.release_id,),
        ),
    )
    with sqlite3.connect(db_path) as connection:
        for statement, parameters in statements:
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(statement, parameters)


def test_audit_only_aggregate_can_publish_without_synthesis(tmp_path):
    db_path, repository, run, draft, metadata, _ = _setup(tmp_path)
    repository.save_aggregate(
        ContextAggregate(
            aggregate_id="aggregate-audit",
            project_id="project-1",
            aggregate_type="event",
            aggregate_key="event:audit",
            payload={"audit_only": True},
            contribution_ids=["contribution-1"],
        )
    )
    release = ContextPublicationRepository(str(db_path)).publish_draft(
        draft.draft_id,
        metadata,
        ["aggregate-audit"],
        [],
        analysis_run_id=run.run_id,
    )

    assert release.release_id
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM context_release_syntheses WHERE release_id = ?",
            (release.release_id,),
        ).fetchone()[0] == 0


def test_legacy_v16_database_upgrade_adds_publication_constraints(tmp_path):
    db_path = tmp_path / "legacy-v16.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
    for version, name, migration in MAIN_DB_MIGRATIONS[:-2]:
        migration(str(db_path))
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, 'now')",
                (version, name),
            )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION
    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(context_releases)")
        }
        assert "analysis_run_id" in columns
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(context_release_syntheses)"
        ).fetchall()
        assert any(row[2] == "context_release_aggregates" and row[4] == "aggregate_id" for row in foreign_keys)
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'context_release_seals'"
        ).fetchone()[0] == 1


def test_publication_migration_preserves_preexisting_unrelated_fk_debt(tmp_path):
    db_path = tmp_path / "legacy-with-orphan.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations "
            "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
    for version, name, migration in MAIN_DB_MIGRATIONS[:-1]:
        migration(str(db_path))
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) "
                "VALUES (?, ?, 'now')",
                (version, name),
            )
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE legacy_parent (id TEXT PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE legacy_child ("
            "id TEXT PRIMARY KEY, parent_id TEXT REFERENCES legacy_parent(id))"
        )
        connection.execute(
            "INSERT INTO legacy_child (id, parent_id) VALUES ('child-1', 'missing-parent')"
        )

    assert migrate_main_database(str(db_path)) == MAIN_DB_TARGET_VERSION

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(context_releases)")
        }
        assert "analysis_run_id" in columns
        assert connection.execute("PRAGMA foreign_key_check(legacy_child)").fetchall()
