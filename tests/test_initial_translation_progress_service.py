import json
import logging

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


def test_build_checkpoint_manager_clears_checkpoint_when_resume_disabled(tmp_path):
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
    assert not checkpoint_path.exists()


def test_emit_progress_keeps_callback_payload_contract():
    events = []
    state = LanguageRunState(completed_batches=3, error_count=1, glossary_issues=2)

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
            "error_count": 1,
            "glossary_issues": 2,
            "format_issues": 4,
            "format_repair": {"detected_count": 4, "fixed_count": 3, "remaining_count": 1},
            "workshop_progress": {"detected_count": 4, "processed_count": 2, "reflection_round": 1},
            "log_message": "validation complete",
        }
    ]


def test_progress_log_bridge_filters_status_poll_noise():
    messages = []
    logger = logging.getLogger()
    original_level = logger.level

    try:
        logger.setLevel(logging.INFO)
        with progress_log_bridge(lambda **payload: messages.append(payload["log_message"])):
            logging.info("translation heartbeat")
            logging.info("GET /api/status HTTP/1.1")
    finally:
        logger.setLevel(original_level)

    assert any("translation heartbeat" in message for message in messages)
    assert not any("GET /api/status" in message for message in messages)
    assert all(logger_handler.__class__.__name__ != "CallbackHandler" for logger_handler in logger.handlers)
