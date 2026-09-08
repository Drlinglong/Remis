import json
import logging
from types import SimpleNamespace

from scripts.core.services.initial_translation_progress_service import (
    LanguageRunState,
    build_checkpoint_manager,
    emit_progress,
    progress_log_bridge,
)


def test_build_checkpoint_manager_uses_per_language_metadata(tmp_path):
    manager = build_checkpoint_manager(
        str(tmp_path),
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        source_lang={"code": "en"},
        target_lang={"code": "zh-CN"},
        use_resume=True,
    )

    assert manager.CHECKPOINT_FILENAME == ".remis_checkpoint_zh-CN.json"
    assert manager.metadata["model_name"] == "gemini-2.5-flash"
    assert manager.metadata["source_lang"] == "en"
    assert manager.metadata["target_lang_code"] == "zh-CN"


def test_build_checkpoint_manager_preserves_checkpoint_when_reads_are_disabled(tmp_path):
    checkpoint_path = tmp_path / ".remis_checkpoint_ja.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "model_name": "old-model",
                    "source_lang": "en",
                    "target_lang_code": "ja",
                },
                "completed_files": ["old.yml"],
            }
        ),
        encoding="utf-8",
    )

    manager = build_checkpoint_manager(
        str(tmp_path),
        selected_provider="ollama",
        model_name=None,
        source_lang={"code": "en"},
        target_lang={"code": "ja"},
        use_resume=False,
    )

    assert manager.CHECKPOINT_FILENAME == ".remis_checkpoint_ja.json"
    assert checkpoint_path.exists()
    assert manager.read_enabled is False
    assert manager.is_file_completed("old.yml") is False
    assert manager.completed_files == set()

    manager.mark_file_completed("new.yml")

    saved = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert saved["completed_files"] == ["new.yml"]


def test_language_run_state_starts_fresh_when_checkpoint_reads_are_disabled():
    state = LanguageRunState.from_checkpoint(SimpleNamespace(
        read_enabled=False,
        progress={"completed_batches": 5, "successful_batches": 4, "failed_batches": 1},
        metadata={"completed_batches": 2},
    ))

    assert state.checkpoint_progress() == {
        "completed_batches": 0,
        "successful_batches": 0,
        "failed_batches": 0,
    }


def test_build_checkpoint_manager_carries_v2_recovery_identity(tmp_path):
    source_root = tmp_path / "source"
    manager = build_checkpoint_manager(
        str(tmp_path / "output"),
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        source_lang={"code": "en"},
        target_lang={"code": "zh-CN"},
        use_resume=True,
        context_metadata={
            "context_release_id": "release-213",
            "source_snapshot_hash": "source-sha-213",
        },
        task_id="task-213",
        run_id="run-213",
        project_id="project-213",
        source_root=str(source_root),
    )

    assert manager.identity["task_id"] == "task-213"
    assert manager.identity["run_id"] == "run-213"
    assert manager.identity["project_id"] == "project-213"
    assert manager.identity["source_snapshot_hash"] == "source-sha-213"
    assert manager.identity["config_fingerprint"]
    assert str(manager.source_root) == str(source_root.resolve())
    assert manager.read_enabled is True


def test_language_run_state_hydrates_cumulative_batch_counters():
    state = LanguageRunState.from_checkpoint(SimpleNamespace(
        progress={"completed_batches": 5, "successful_batches": 4, "failed_batches": 1},
        metadata={"completed_batches": 2},
    ))

    assert state.checkpoint_progress() == {
        "completed_batches": 5,
        "successful_batches": 4,
        "failed_batches": 1,
    }


def test_emit_progress_keeps_callback_payload_contract():
    events = []
    state = LanguageRunState(
        completed_batches=3,
        successful_batches=2,
        failed_batches=1,
        error_count=1,
        glossary_issues=2,
    )

    emit_progress(
        lambda **payload: events.append(payload),
        state,
        total_batches=7,
        current_file_name="events_l_english.yml",
        stage="Verifying",
        log_message="validation complete",
        format_issues_override=4,
        format_repair={"detected_count": 4, "fixed_count": 3, "remaining_count": 1},
        workshop_progress={"detected_count": 4, "processed_count": 2, "reflection_round": 1},
    )

    assert state.format_issues == 4
    assert events == [
        {
            "current": 3,
            "total": 7,
            "current_file": "events_l_english.yml",
            "stage": "Verifying",
            "current_batch": 3,
            "total_batches": 7,
            "successful_batches": 2,
            "failed_batches": 1,
            "error_count": 1,
            "glossary_issues": 2,
            "glossary_issue_details": [],
            "recovered_retries": 0,
            "format_issues": 4,
            "format_repair": {"detected_count": 4, "fixed_count": 3, "remaining_count": 1},
            "workshop_progress": {"detected_count": 4, "processed_count": 2, "reflection_round": 1},
            "log_message": "validation complete",
            "event_level": None,
        }
    ]


def test_progress_log_bridge_filters_status_poll_noise_and_preserves_level():
    messages = []
    logger = logging.getLogger()
    original_level = logger.level

    try:
        logger.setLevel(logging.INFO)
        with progress_log_bridge(lambda **payload: messages.append(payload)):
            logging.info("translation heartbeat")
            logging.warning("potential glossary issue")
            logging.info("GET /api/status HTTP/1.1")
    finally:
        logger.setLevel(original_level)

    assert any(
        "translation heartbeat" in item["log_message"] and item["event_level"] == "info"
        for item in messages
    )
    assert any(
        "potential glossary issue" in item["log_message"] and item["event_level"] == "warning"
        for item in messages
    )
    assert not any("GET /api/status" in item["log_message"] for item in messages)
    assert all(logger_handler.__class__.__name__ != "CallbackHandler" for logger_handler in logger.handlers)
