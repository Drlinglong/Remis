"""Failing contract tests for task-owned translation checkpoint v2."""

import json

import pytest

from scripts.core.checkpoint_manager import CheckpointManager


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
