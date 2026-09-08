"""Failing contract tests for task-owned translation checkpoint v2."""

import json

import pytest

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import FileTask
from scripts.core.services import initial_translation_language_service as language_service
from scripts.core.services.initial_translation_progress_service import LanguageRunState


IDENTITY = {
    "task_id": "task-213",
    "run_id": "run-213",
    "project_id": "project-213",
    "config_fingerprint": "config-sha-1",
    "source_snapshot_hash": "source-sha-1",
}
CURRENT_CONFIG = {
    "model_name": "test-model",
    "source_lang": "english",
    "target_lang_code": "zh-CN",
}


def _manager(output_dir, source_root, **overrides):
    identity = {**IDENTITY, **overrides}
    return CheckpointManager(
        str(output_dir),
        current_config=CURRENT_CONFIG,
        source_root=str(source_root),
        task_id=identity["task_id"],
        run_id=identity["run_id"],
        project_id=identity["project_id"],
        config_fingerprint=identity["config_fingerprint"],
        source_snapshot_hash=identity["source_snapshot_hash"],
    )


def _file_task(file_path="nested/demo.yml", texts=None):
    texts = list(texts or ["one", "two", "three"])
    return FileTask(
        filename="demo.yml",
        root=".",
        original_lines=[],
        texts_to_translate=texts,
        key_map={},
        is_custom_loc=False,
        target_lang={"code": "zh-CN", "name": "Simplified Chinese"},
        source_lang={"code": "en", "name": "English"},
        game_profile={},
        mod_context="",
        provider_name="test",
        output_folder_name="out",
        source_dir=".",
        dest_dir=".",
        client=object(),
        mod_name="Demo",
        file_path=file_path,
        translation_entry_indices=list(range(len(texts))),
    )


def test_v2_checkpoint_persists_ownership_compatibility_and_progress(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_file = source_root / "localization" / "foo.yml"
    source_file.parent.mkdir(parents=True)
    output_dir.mkdir()

    manager = _manager(output_dir, source_root)
    manager.mark_file_completed(
        str(source_file),
        progress_metadata={
            "completed_batches": 4,
            "successful_batches": 3,
            "failed_batches": 1,
        },
    )

    restored = _manager(output_dir, source_root)
    info = restored.get_checkpoint_info()

    assert info["compatibility"] == "compatible"
    assert info["resume_allowed"] is True
    assert info["identity"] == IDENTITY
    assert info["completed_files"] == ["localization/foo.yml"]
    assert info["progress"] == {
        "completed_batches": 4,
        "successful_batches": 3,
        "failed_batches": 1,
    }
    assert restored.is_file_completed("localization/foo.yml") is True


def test_checkpoint_persists_restorable_batch_before_any_file_completes(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    manager = _manager(output_dir, source_root)
    manager.mark_batch_completed(
        "localization/foo.yml",
        batch_index=0,
        start_index=0,
        end_index=2,
        source_texts=["Hello $NAME$", "Open [Concept('market')]"],
        source_entry_indices=[0, 1],
        translated_texts=["你好 $NAME$", "打开 [Concept('market')]"],
        warnings=[{"type": "format_validation", "message": "kept"}],
        progress_metadata={
            "completed_batches": 1,
            "successful_batches": 1,
            "failed_batches": 0,
        },
    )

    restored = _manager(output_dir, source_root)
    batch = restored.restore_batch(
        "localization/foo.yml",
        batch_index=0,
        start_index=0,
        end_index=2,
        source_texts=["Hello $NAME$", "Open [Concept('market')]"],
        source_entry_indices=[0, 1],
    )
    info = restored.get_checkpoint_info()

    assert batch == {
        "translated_texts": ["你好 $NAME$", "打开 [Concept('market')]"],
        "warnings": [{"type": "format_validation", "message": "kept"}],
    }
    assert info["completed_count"] == 0
    assert info["completed_batch_count"] == 1
    assert info["resume_allowed"] is True


def test_checkpoint_rejects_batch_when_source_partition_changes(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    manager = _manager(output_dir, source_root)
    manager.mark_batch_completed(
        "localization/foo.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["Original"],
        source_entry_indices=[0],
        translated_texts=["译文"],
    )

    assert manager.restore_batch(
        "localization/foo.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["Changed"],
        source_entry_indices=[0],
    ) is None


def test_checkpoint_batch_updates_are_out_of_order_safe_and_idempotent(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    manager = _manager(output_dir, source_root)

    for batch_index, source, translated in (
        (1, "second", "第二"),
        (0, "first", "第一"),
        (1, "second", "第二"),
    ):
        manager.mark_batch_completed(
            "localization/foo.yml",
            batch_index=batch_index,
            start_index=batch_index,
            end_index=batch_index + 1,
            source_texts=[source],
            source_entry_indices=[batch_index],
            translated_texts=[translated],
        )

    first_reload = _manager(output_dir, source_root)
    second_reload = _manager(output_dir, source_root)

    assert first_reload.get_checkpoint_info()["completed_batch_count"] == 2
    assert second_reload.get_checkpoint_info()["completed_batches"] == {
        "localization/foo.yml": [0, 1],
    }
    assert second_reload.restore_batch(
        "localization/foo.yml",
        batch_index=1,
        start_index=1,
        end_index=2,
        source_texts=["second"],
        source_entry_indices=[1],
    )["translated_texts"] == ["第二"]


def test_v2_file_checkpoint_progress_remains_monotonic_after_v3_batch_save(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / ".remis_checkpoint.json").write_text(
        json.dumps({
            "schema_version": 2,
            "identity": IDENTITY,
            "completed_files": ["localization/done.yml"],
            "progress": {
                "completed_batches": 4,
                "successful_batches": 4,
                "failed_batches": 0,
            },
        }),
        encoding="utf-8",
    )
    manager = _manager(output_dir, source_root)

    manager.mark_batch_completed(
        "localization/pending.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["pending"],
        source_entry_indices=[0],
        translated_texts=["待处理"],
    )

    restored = _manager(output_dir, source_root)
    assert restored.get_checkpoint_info()["progress"] == {
        "completed_batches": 5,
        "successful_batches": 5,
        "failed_batches": 0,
    }


def test_language_run_restores_saved_batch_without_model_resubmission(monkeypatch, tmp_path):
    model_calls = []
    finalized = []

    class Handler:
        def translate_batch(self, batch_task):
            model_calls.append(batch_task.batch_index)
            batch_task.translated_texts = [f"new-{batch_task.batch_index}"]
            return batch_task

    file_task = _file_task()
    monkeypatch.setattr(
        language_service,
        "finalize_translated_file",
        lambda *args, **kwargs: finalized.append((args, kwargs)),
    )
    monkeypatch.setattr(language_service, "log_batch_warnings", lambda *_args: None)
    monkeypatch.setattr(language_service, "log_recovered_retries", lambda *_args: None)

    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    checkpoint = _manager(output_dir, source_root)
    checkpoint.resume_enabled = True
    checkpoint.mark_batch_completed(
        "nested/demo.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["one"],
        source_entry_indices=[0],
        translated_texts=["saved-0"],
    )
    checkpoint = _manager(output_dir, source_root)
    checkpoint.resume_enabled = True
    run_state = LanguageRunState.from_checkpoint(checkpoint)
    language_service._process_file_tasks(
        processor=ParallelProcessor(max_workers=1, chunk_size_override=1),
        file_task_generator=iter([file_task]),
        handler=Handler(),
        progress_lock=language_service.threading.Lock(),
        run_state=run_state,
        update_progress=lambda *_args, **_kwargs: None,
        rpm_limit=None,
        target_lang=file_task.target_lang,
        output_folder_name="out",
        game_profile={},
        proofreading_tracker=object(),
        checkpoint_manager=checkpoint,
        project_id="project-1",
        version_id=1,
        all_files_content=[],
        total_batches=3,
    )

    assert model_calls == [1, 2]
    assert finalized[0][0][1] == ["saved-0", "new-1", "new-2"]
    assert run_state.completed_batches == 3
    assert run_state.successful_batches == 3
    assert _manager(output_dir, source_root).get_checkpoint_info()["completed_batch_count"] == 3


def test_failed_batch_is_retried_while_successful_batches_are_restored(monkeypatch, tmp_path):
    finalized = []
    first_calls = []
    second_calls = []

    class FirstHandler:
        def translate_batch(self, batch_task):
            first_calls.append(batch_task.batch_index)
            if batch_task.batch_index == 1:
                batch_task.failed = True
                batch_task.fell_back_to_source = True
                batch_task.translated_texts = list(batch_task.texts)
            else:
                batch_task.translated_texts = [f"saved-{batch_task.batch_index}"]
            return batch_task

    class SecondHandler:
        def translate_batch(self, batch_task):
            second_calls.append(batch_task.batch_index)
            batch_task.translated_texts = [f"retried-{batch_task.batch_index}"]
            return batch_task

    monkeypatch.setattr(
        language_service,
        "finalize_translated_file",
        lambda *args, **kwargs: finalized.append((args, kwargs)),
    )
    monkeypatch.setattr(language_service, "log_batch_warnings", lambda *_args: None)
    monkeypatch.setattr(language_service, "log_recovered_retries", lambda *_args: None)
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    checkpoint = _manager(output_dir, source_root)
    checkpoint.resume_enabled = True
    first_state = LanguageRunState()
    common = {
        "processor": ParallelProcessor(max_workers=1, chunk_size_override=1),
        "progress_lock": language_service.threading.Lock(),
        "update_progress": lambda *_args, **_kwargs: None,
        "rpm_limit": None,
        "target_lang": _file_task().target_lang,
        "output_folder_name": "out",
        "game_profile": {},
        "proofreading_tracker": object(),
        "project_id": "project-1",
        "version_id": 1,
        "all_files_content": [],
        "total_batches": 3,
    }
    language_service._process_file_tasks(
        file_task_generator=iter([_file_task()]),
        handler=FirstHandler(),
        run_state=first_state,
        checkpoint_manager=checkpoint,
        **common,
    )

    restored_checkpoint = _manager(output_dir, source_root)
    restored_checkpoint.resume_enabled = True
    assert restored_checkpoint.get_checkpoint_info()["completed_batches"] == {
        "nested/demo.yml": [0, 2],
    }
    second_state = LanguageRunState.from_checkpoint(restored_checkpoint)
    language_service._process_file_tasks(
        file_task_generator=iter([_file_task()]),
        handler=SecondHandler(),
        run_state=second_state,
        checkpoint_manager=restored_checkpoint,
        **common,
    )

    assert first_calls == [0, 1, 2]
    assert second_calls == [1]
    assert finalized[-1][0][1] == ["saved-0", "retried-1", "saved-2"]
    assert second_state.completed_batches == 3
    assert second_state.successful_batches == 3


def test_stream_processor_isolates_same_basename_by_stable_file_path():
    tasks = [
        _file_task("events/a/demo.yml", ["alpha"]),
        _file_task("events/b/demo.yml", ["beta"]),
    ]

    def translate(batch_task):
        batch_task.translated_texts = [f"translated-{batch_task.texts[0]}"]
        return batch_task

    results = list(
        ParallelProcessor(max_workers=2, chunk_size_override=1).process_files_stream(
            iter(tasks),
            translate,
        )
    )

    assert {
        file_task.file_path: translated_texts
        for file_task, translated_texts, _warnings, _failed in results
    } == {
        "events/a/demo.yml": ["translated-alpha"],
        "events/b/demo.yml": ["translated-beta"],
    }


def test_completed_file_compacts_batch_payload_without_losing_progress(tmp_path):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    manager = _manager(output_dir, source_root)
    manager.mark_batch_completed(
        "localization/foo.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["source"],
        source_entry_indices=[0],
        translated_texts=["译文"],
    )

    manager.mark_file_completed(
        "localization/foo.yml",
        progress_metadata={
            "completed_batches": 1,
            "successful_batches": 1,
            "failed_batches": 0,
        },
    )
    restored = _manager(output_dir, source_root)

    assert restored.get_checkpoint_info()["completed_files"] == ["localization/foo.yml"]
    assert restored.get_checkpoint_info()["completed_batch_count"] == 0
    assert restored.get_checkpoint_info()["progress"]["successful_batches"] == 1


def test_legacy_checkpoint_is_explicitly_incompatible(tmp_path):
    output_dir = tmp_path / "output"
    source_root = tmp_path / "source"
    output_dir.mkdir()
    (output_dir / ".remis_checkpoint.json").write_text(
        json.dumps(
            {
                "metadata": {"model_name": "test-model"},
                "completed_files": ["localization/foo.yml"],
            }
        ),
        encoding="utf-8",
    )

    info = _manager(output_dir, source_root).get_checkpoint_info()

    assert info["compatibility"] == "incompatible"
    assert info["compatibility_reason"] == "legacy_format"
    assert info["resume_allowed"] is False


def test_corrupt_checkpoint_is_explicitly_reported_and_not_resumable(tmp_path):
    output_dir = tmp_path / "output"
    source_root = tmp_path / "source"
    output_dir.mkdir()
    (output_dir / ".remis_checkpoint.json").write_text(
        '{"completed_files": [',
        encoding="utf-8",
    )

    info = _manager(output_dir, source_root).get_checkpoint_info()

    assert info["compatibility"] == "corrupt"
    assert info["compatibility_reason"] == "corrupt_json"
    assert info["resume_allowed"] is False


@pytest.mark.parametrize(
    "batch_override",
    [
        {"status": "failed"},
        {"batch_index": 1},
        {"end_index": 2},
    ],
)
def test_corrupt_batch_payload_is_not_resumable(tmp_path, batch_override):
    output_dir = tmp_path / "output"
    source_root = tmp_path / "source"
    output_dir.mkdir()
    batch = {
        "batch_index": 0,
        "status": "succeeded",
        "start_index": 0,
        "end_index": 1,
        "source_hash": "sha256",
        "source_entry_indices": [0],
        "translated_texts": ["译文"],
        "warnings": [],
    }
    batch.update(batch_override)
    (output_dir / ".remis_checkpoint.json").write_text(
        json.dumps({
            "schema_version": 3,
            "identity": IDENTITY,
            "completed_files": [],
            "batch_results": {"localization/foo.yml": {"0": batch}},
            "progress": {"completed_batches": 1, "successful_batches": 1},
        }),
        encoding="utf-8",
    )

    info = _manager(output_dir, source_root).get_checkpoint_info()

    assert info["compatibility"] == "corrupt"
    assert info["completed_batch_count"] == 0
    assert info["resume_allowed"] is False


def test_parent_traversal_checkpoint_is_corrupt_and_not_resumable(tmp_path):
    output_dir = tmp_path / "output"
    source_root = tmp_path / "source"
    output_dir.mkdir()
    (output_dir / ".remis_checkpoint.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "identity": IDENTITY,
                "progress": {"completed_batches": 1},
                "completed_files": ["../outside.yml"],
            }
        ),
        encoding="utf-8",
    )

    manager = _manager(output_dir, source_root)
    info = manager.get_checkpoint_info()

    assert info["compatibility"] == "corrupt"
    assert info["compatibility_reason"] == "invalid_file_identity"
    assert info["completed_files"] == []
    assert info["resume_allowed"] is False


def test_mark_file_completed_rejects_parent_traversal(tmp_path):
    output_dir = tmp_path / "output"
    source_root = tmp_path / "source"
    output_dir.mkdir()

    manager = _manager(output_dir, source_root)

    with pytest.raises(ValueError, match="parent traversal"):
        manager.mark_file_completed("../outside.yml")


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("config_fingerprint", "config-sha-2", "config_mismatch"),
        ("source_snapshot_hash", "source-sha-2", "source_snapshot_mismatch"),
    ],
)
def test_source_or_config_mismatch_blocks_resume(tmp_path, field, value, reason):
    source_root = tmp_path / "source"
    output_dir = tmp_path / "output"
    source_file = source_root / "localization" / "foo.yml"
    source_file.parent.mkdir(parents=True)
    output_dir.mkdir()

    _manager(output_dir, source_root).mark_file_completed(str(source_file))
    restored = _manager(output_dir, source_root, **{field: value})
    info = restored.get_checkpoint_info()

    assert info["compatibility"] == "incompatible"
    assert info["compatibility_reason"] == reason
    assert info["resume_allowed"] is False
