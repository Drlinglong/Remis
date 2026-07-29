import sqlite3

import pytest

from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.model_arena_repository import ModelArenaRepository


def _create_project(db_path, project_id="project-1"):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO projects (
                project_id, name, game_id, source_path, source_language, status
            ) VALUES (?, 'Arena Mod', 'vic3', '/tmp/arena', 'english', 'active')
            """,
            (project_id,),
        )


def _draft(project_id="project-1"):
    return {
        "run_id": "run-1",
        "project_id": project_id,
        "project_name_snapshot": "Arena Mod",
        "game_id": "vic3",
        "source_lang_code": "en",
        "target_lang_code": "zh-CN",
        "sample_seed": "seed-1",
        "sampler_version": "stratified-coverage-v1",
        "sample_size": 3,
        "eligible_count": 20,
        "status": "draft",
        "settings": {"use_mod_context": True},
        "created_at": "2026-07-26T00:00:00+00:00",
    }


def _contestants():
    return [
        {
            "contestant_id": f"contestant-{index}",
            "provider_id": "provider",
            "model_id": f"model-{index}",
            "execution_order": index,
            "config_snapshot": {"temperature": "unknown"},
            "config_fingerprint": f"config-{index}",
            "prompt_fingerprint": "prompt",
            "status": "draft",
        }
        for index in range(2)
    ]


def _samples(prefix="sample"):
    return [
        {
            "sample_id": f"{prefix}-{index}",
            "ordinal": index,
            "entry_key": f"key_{index}",
            "relative_file_path": "localization/english/arena_l_english.yml",
            "line_number": index + 2,
            "source_text": f"Source {index}",
            "source_sha256": f"source-hash-{index}",
            "feature_tags": ["length:short"],
            "display_permutation": ["contestant-1", "contestant-0"],
        }
        for index in range(3)
    ]


def test_migration_009_creates_independent_arena_schema(tmp_path):
    db_path = tmp_path / "arena.sqlite"

    assert migrate_main_database(str(db_path)) == 9

    with sqlite3.connect(db_path) as connection:
        migration = connection.execute(
            "SELECT name FROM schema_migrations WHERE version = 9"
        ).fetchone()
        assert migration == ("add_model_arena_history",)
        tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name LIKE 'model_arena_%'
                """
            )
        }
        assert tables == {
            "model_arena_runs",
            "model_arena_contestants",
            "model_arena_requests",
            "model_arena_samples",
            "model_arena_outputs",
            "model_arena_votes",
            "model_arena_events",
        }
        request_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(model_arena_requests)")
        }
        assert {
            "system_instruction",
            "prompt_text",
            "completion_text_before_parse",
            "completion_source",
            "usage_json",
        }.issubset(request_columns)


def test_repository_round_trips_json_and_preserves_run_when_project_is_deleted(tmp_path):
    db_path = tmp_path / "arena.sqlite"
    migrate_main_database(str(db_path))
    _create_project(db_path)
    repository = ModelArenaRepository(str(db_path))

    created = repository.create_run(_draft(), _contestants(), _samples())

    assert created["settings"] == {"use_mod_context": True}
    assert created["contestants"][0]["config_snapshot"] == {
        "temperature": "unknown"
    }
    assert created["samples"][0]["feature_tags"] == ["length:short"]
    assert created["samples"][0]["display_permutation"] == [
        "contestant-1",
        "contestant-0",
    ]

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("DELETE FROM projects WHERE project_id = 'project-1'")
        connection.commit()

    retained = repository.get_run("run-1")
    assert retained["project_id"] is None
    assert retained["project_name_snapshot"] == "Arena Mod"


def test_repository_evidence_vote_event_and_run_delete_cascade(tmp_path):
    db_path = tmp_path / "arena.sqlite"
    migrate_main_database(str(db_path))
    _create_project(db_path)
    repository = ModelArenaRepository(str(db_path))
    repository.create_run(_draft(), _contestants(), _samples())

    repository.insert_requests(
        [
            {
                "request_id": "request-1",
                "contestant_id": "contestant-0",
                "batch_ordinal": 0,
                "system_instruction": "Translate faithfully.",
                "prompt_text": "Translate these strings.",
                "effective_parameters": {"temperature": 0},
                "prompt_sha256": "prompt-hash",
                "completion_text_before_parse": '["译文"]',
                "completion_source": "assistant_content",
                "completion_sha256": "completion-hash",
                "usage": {"input_tokens": 10, "output_tokens": 3},
                "parse_status": "parsed",
                "elapsed_ms": 25,
            }
        ]
    )
    repository.insert_outputs(
        [
            {
                "output_id": "output-1",
                "sample_id": "sample-0",
                "contestant_id": "contestant-0",
                "translated_text": "译文",
                "response_sha256": "response-hash",
                "parse_status": "parsed",
                "hard_error_count": 0,
                "validation": [],
            }
        ]
    )
    first_vote = repository.upsert_vote(
        {
            "vote_id": "vote-1",
            "sample_id": "sample-0",
            "verdict": "winner",
            "winner_output_id": "output-1",
            "reason_codes": ["faithful"],
            "note": "更贴近原文",
        }
    )
    updated_vote = repository.upsert_vote(
        {
            "vote_id": "ignored-on-update",
            "sample_id": "sample-0",
            "verdict": "tie",
            "winner_output_id": None,
            "reason_codes": [],
        }
    )
    event = repository.append_event(
        "run-1",
        {"event_type": "request_completed", "metrics": {"elapsed_ms": 25}},
    )
    contestant = repository.update_contestant(
        "contestant-0",
        status="completed",
        request_count=1,
        elapsed_ms=25,
        failure_code=None,
    )

    assert first_vote["reason_codes"] == ["faithful"]
    assert updated_vote["vote_id"] == "vote-1"
    assert updated_vote["verdict"] == "tie"
    assert event["sequence"] == 1
    assert contestant["status"] == "completed"
    assert contestant["request_count"] == 1
    detail = repository.get_run("run-1")
    assert detail["requests"][0]["completion_text_before_parse"] == '["译文"]'
    assert detail["outputs"][0]["validation"] == []
    assert detail["events"][0]["metrics"] == {"elapsed_ms": 25}

    assert repository.delete_run("run-1") is True
    assert repository.get_run("run-1") is None
    with sqlite3.connect(db_path) as connection:
        for table in (
            "model_arena_contestants",
            "model_arena_requests",
            "model_arena_samples",
            "model_arena_outputs",
            "model_arena_votes",
            "model_arena_events",
        ):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_replace_samples_is_limited_to_draft_runs(tmp_path):
    db_path = tmp_path / "arena.sqlite"
    migrate_main_database(str(db_path))
    _create_project(db_path)
    repository = ModelArenaRepository(str(db_path))
    repository.create_run(_draft(), _contestants(), _samples())

    replaced = repository.replace_samples(
        "run-1",
        _samples("replacement"),
        sample_seed="seed-2",
        eligible_count=30,
    )
    assert replaced["sample_seed"] == "seed-2"
    assert replaced["eligible_count"] == 30
    assert replaced["samples"][0]["sample_id"] == "replacement-0"

    repository.update_run("run-1", status="queued")
    with pytest.raises(ValueError, match="only be replaced"):
        repository.replace_samples("run-1", _samples("again"))


def test_repository_rejects_secrets_in_contestant_config_snapshot(tmp_path):
    db_path = tmp_path / "arena.sqlite"
    migrate_main_database(str(db_path))
    _create_project(db_path)
    repository = ModelArenaRepository(str(db_path))
    contestants = _contestants()
    contestants[1]["config_snapshot"] = {
        "temperature": 0,
        "credentials": {"api_key": "must-not-be-persisted"},
    }

    with pytest.raises(ValueError, match="Sensitive field"):
        repository.create_run(_draft(), contestants, _samples())

    assert repository.get_run("run-1") is None
