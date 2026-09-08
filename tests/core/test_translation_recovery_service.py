from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.db_migrations import migrate_main_database
from scripts.core.repositories.task_repository import TaskRepository
from scripts.core.services.translation_recovery_service import (
    TranslationRecoveryService,
    build_recovery_descriptor,
    canonical_configuration,
    source_tree_hash,
)
from scripts.core.services import translation_recovery_service
from scripts.core.services.initial_translation_start_service import (
    create_initial_translation_task,
)
from scripts.core.services.translation_task_runtime import prepare_initial_recovery
from scripts.core.services import translation_task_runtime
from scripts.core.services.translation_task_lifecycle import TranslationTaskLifecycle
from scripts.routers import translation_recovery
from scripts.schemas.translation import ResumeTranslationTaskRequest
from scripts.shared import task_state


def _repository(tmp_path):
    db_path = tmp_path / "recovery.sqlite"
    migrate_main_database(str(db_path))
    return TaskRepository(str(db_path))


def _checkpoint(recovery, target_code="zh-CN"):
    return CheckpointManager(
        recovery["output_dir"],
        checkpoint_filename=f".remis_checkpoint_{target_code}.json",
        source_root=recovery["source_root"],
        task_id=recovery["checkpoint_owner_task_id"],
        run_id=recovery["checkpoint_owner_run_id"],
        project_id=recovery["project_id"],
        config_fingerprint=recovery["config_fingerprint"],
        source_snapshot_hash=recovery["source_snapshot_hash"],
    )


def test_recovery_projection_reads_only_the_task_owned_checkpoint(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-original",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1", "source_lang_code": "en"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-original",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    _checkpoint(recovery).mark_file_completed(str(source_file))

    projection = TranslationRecoveryService(repository).inspect("project-1")

    assert projection["checkpoint"]["compatibility"] == "compatible"
    assert projection["checkpoint"]["completed_units"] == 1
    assert "resume_task" in projection["allowed_actions"]


@pytest.mark.parametrize("status", ["interrupted", "failed", "cancelled"])
def test_recovery_projection_reports_batch_checkpoint_without_completed_file(tmp_path, status):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-batch",
        project_id="project-batch",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-batch", "source_lang_code": "en"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-batch",
        "kind": "initial_translation",
        "project_id": "project-batch",
        "status": status,
        "created_at": "2026-09-05T00:00:00Z",
        "updated_at": "2026-09-05T00:01:00Z",
        "recovery": recovery,
    })
    _checkpoint(recovery).mark_batch_completed(
        "localization.yml",
        batch_index=0,
        start_index=0,
        end_index=1,
        source_texts=["Value"],
        source_entry_indices=[0],
        translated_texts=["值"],
    )

    projection = TranslationRecoveryService(repository).inspect("project-batch")

    assert projection["checkpoint"]["granularity"] == "batch"
    assert projection["checkpoint"]["completed_units"] == 0
    assert projection["checkpoint"]["completed_batches"] == 1
    assert projection["checkpoint"]["targets"][0]["completed_batch_count"] == 1
    assert "resume_task" in projection["allowed_actions"]


@pytest.mark.parametrize("status", ["processing", "completed"])
def test_start_over_rejects_non_interrupted_tasks_without_clearing_checkpoint(tmp_path, status):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id=f"task-{status}",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": f"task-{status}",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": status,
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    checkpoint = _checkpoint(recovery)
    checkpoint.mark_file_completed(str(source_file))
    checkpoint_bytes = checkpoint.checkpoint_path
    with open(checkpoint_bytes, "rb") as checkpoint_file:
        original_contents = checkpoint_file.read()

    service = TranslationRecoveryService(repository)
    with pytest.raises(ValueError, match="does not allow start over"):
        service.require_start_over(f"task-{status}")

    with open(checkpoint_bytes, "rb") as checkpoint_file:
        assert checkpoint_file.read() == original_contents
    assert repository.get_task(f"task-{status}")["status"] == status


def test_start_over_clears_checkpoint_only_after_replacement_owns_lock(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-interrupted",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-interrupted",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    checkpoint = _checkpoint(recovery)
    checkpoint.mark_file_completed(str(source_file))
    service = TranslationRecoveryService(repository)

    service.require_start_over("task-interrupted")
    with pytest.raises(ValueError, match="does not own"):
        service.finalize_start_over(
            "task-interrupted",
            replacement_task_id="task-replacement",
        )
    assert _checkpoint(recovery).get_checkpoint_info()["exists"] is True

    repository.save_task({
        "task_id": "task-replacement",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "queued",
        "created_at": "2026-08-31T00:02:00Z",
        "updated_at": "2026-08-31T00:02:00Z",
    })
    assert repository.acquire_project_lock(
        task_id="task-replacement",
        project_id="project-1",
    ) is True

    service.finalize_start_over(
        "task-interrupted",
        replacement_task_id="task-replacement",
    )

    assert _checkpoint(recovery).get_checkpoint_info()["exists"] is False
    assert repository.get_task("task-interrupted")["checkpoint"]["available"] is False


def test_explicit_project_clear_removes_checkpoint_slot(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-interrupted",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-interrupted",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    checkpoint = _checkpoint(recovery)
    checkpoint.mark_file_completed(str(source_file))
    stale_target_checkpoint = _checkpoint(recovery, target_code="ja")
    stale_target_checkpoint.mark_file_completed(str(source_file))
    service = TranslationRecoveryService(repository)

    inspection = service.inspect("project-1")
    assert "clear_checkpoint" in inspection["allowed_actions"]
    assert inspection["checkpoint"]["resumable"] is True
    assert [target["target_lang_code"] for target in inspection["checkpoint"]["targets"]] == ["zh-CN"]
    projection = service.clear_project_checkpoint("project-1")

    assert checkpoint.get_checkpoint_info()["exists"] is False
    assert stale_target_checkpoint.get_checkpoint_info()["exists"] is False
    assert projection["checkpoint"]["available"] is False
    assert "clear_checkpoint" not in projection["allowed_actions"]
    assert repository.get_task("task-interrupted")["checkpoint"]["metadata"] == {
        "cleared_by_user": True,
    }


def test_resume_rejects_stale_checkpoint_revision(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-revision",
        project_id="project-revision",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-revision"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-revision",
        "kind": "initial_translation",
        "project_id": "project-revision",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    _checkpoint(recovery).mark_file_completed(str(source_file))
    service = TranslationRecoveryService(repository)
    revision = service.inspect("project-revision")["checkpoint"]["revision"]

    assert service.require_resumable(
        "task-revision",
        expected_checkpoint_revision=revision,
    )["task_id"] == "task-revision"
    with pytest.raises(ValueError, match="checkpoint revision changed"):
        service.require_resumable(
            "task-revision",
            expected_checkpoint_revision=revision + 1,
        )


def test_explicit_project_clear_rejects_active_writer(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text('l_english:\n key:0 "Value"\n', encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-active",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-active",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "processing",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    checkpoint = _checkpoint(recovery)
    checkpoint.mark_file_completed(str(source_file))

    with pytest.raises(ValueError, match="while translation is active"):
        TranslationRecoveryService(repository).clear_project_checkpoint("project-1")

    assert checkpoint.get_checkpoint_info()["exists"] is True


def test_latest_completed_translation_supersedes_older_cancelled_recovery(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "localization.yml").write_text(
        "l_english:\n key:0 \"Value\"\n",
        encoding="utf-8",
    )
    old_recovery = build_recovery_descriptor(
        task_id="445501a1-b194-459c-9869-a08b4608ce8b",
        project_id="ae507ae2-2a08-44e3-9c3d-caa4445911f2",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "ae507ae2-2a08-44e3-9c3d-caa4445911f2"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "445501a1-b194-459c-9869-a08b4608ce8b",
        "kind": "initial_translation",
        "project_id": "ae507ae2-2a08-44e3-9c3d-caa4445911f2",
        "status": "cancelled",
        "created_at": "2026-08-31T23:34:00Z",
        "updated_at": "2026-08-31T23:35:00Z",
        "recovery": old_recovery,
    })
    repository.save_task({
        "task_id": "39cd8c20-755e-4205-a885-e3b7925362e6",
        "kind": "initial_translation",
        "project_id": "ae507ae2-2a08-44e3-9c3d-caa4445911f2",
        "status": "completed",
        "created_at": "2026-08-31T23:44:00Z",
        "updated_at": "2026-08-31T23:45:00Z",
        "recovery": build_recovery_descriptor(
            task_id="39cd8c20-755e-4205-a885-e3b7925362e6",
            project_id="ae507ae2-2a08-44e3-9c3d-caa4445911f2",
            source_root=str(source_root),
            output_dir=str(tmp_path / "new-output"),
            target_lang_codes=["zh-CN"],
            configuration={"project_id": "ae507ae2-2a08-44e3-9c3d-caa4445911f2"},
            snapshot_hash=source_tree_hash(str(source_root)),
        ),
    })

    service = TranslationRecoveryService(repository)
    assert service.latest_recovery_task(
        "ae507ae2-2a08-44e3-9c3d-caa4445911f2"
    )["task_id"] == "39cd8c20-755e-4205-a885-e3b7925362e6"
    projection = service.inspect("ae507ae2-2a08-44e3-9c3d-caa4445911f2")

    assert projection["task_id"] == "39cd8c20-755e-4205-a885-e3b7925362e6"
    assert projection["status"] == "completed"
    assert projection["checkpoint"]["available"] is False
    assert projection["checkpoint"]["resumable"] is False
    assert projection["allowed_actions"] == ["view_task", "archive_task"]


def test_continuation_preserves_checkpoint_owner_and_rejects_config_drift(tmp_path):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "localization.yml").write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    request_payload = {
        "project_id": "project-1",
        "source_lang_code": "en",
        "target_lang_codes": ["zh-CN"],
        "api_provider": "gemini",
        "model": "model-1",
        "use_resume": True,
    }
    configuration = canonical_configuration(request_payload)
    parent_recovery = build_recovery_descriptor(
        task_id="task-original",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration=configuration,
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-original",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": parent_recovery,
    })
    _checkpoint(parent_recovery).mark_file_completed(str(source_root / "localization.yml"))
    previous_repository = task_state.get_repository()
    try:
        task_state.configure_repository(repository, hydrate=False)
        request = SimpleNamespace(
            project_id="project-1",
            resume_from_task_id="task-original",
            model_dump=lambda mode=None: {**request_payload, "resume_from_task_id": "task-original"},
        )
        _, continuation = prepare_initial_recovery(
            request=request,
            project={"source_path": str(source_root)},
            task_id="task-continuation",
            target_languages=[{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
        )
        assert continuation["checkpoint_owner_task_id"] == "task-original"
        assert continuation["checkpoint_owner_run_id"] == "task-original"

        request_payload["model"] = "model-2"
        try:
            prepare_initial_recovery(
                request=request,
                project={"source_path": str(source_root)},
                task_id="task-drifted",
                target_languages=[{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
            )
        except ValueError as exc:
            assert "configuration changed" in str(exc)
        else:
            raise AssertionError("Configuration drift must block checkpoint continuation")
    finally:
        task_state.configure_repository(previous_repository, hydrate=False)


def test_continuation_uses_one_validated_source_hash(tmp_path, monkeypatch):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    source_file = source_root / "localization.yml"
    source_file.write_text("l_english:\n key:0 \"Value\"\n", encoding="utf-8")
    request_payload = {
        "project_id": "project-hash",
        "source_lang_code": "en",
        "target_lang_codes": ["zh-CN"],
        "api_provider": "gemini",
        "model": "model-1",
        "use_resume": True,
    }
    parent_recovery = build_recovery_descriptor(
        task_id="task-hash-original",
        project_id="project-hash",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration=canonical_configuration(request_payload),
        snapshot_hash="source-before",
    )
    repository.save_task({
        "task_id": "task-hash-original",
        "kind": "initial_translation",
        "project_id": "project-hash",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": parent_recovery,
    })
    _checkpoint(parent_recovery).mark_file_completed(str(source_file))
    source_hash = Mock(side_effect=["source-before", "source-after"])
    monkeypatch.setattr(
        translation_task_runtime,
        "source_tree_hash",
        source_hash,
    )
    monkeypatch.setattr(translation_recovery_service, "source_tree_hash", source_hash)
    request = SimpleNamespace(
        project_id="project-hash",
        resume_from_task_id="task-hash-original",
        model_dump=lambda mode=None: {
            **request_payload,
            "resume_from_task_id": "task-hash-original",
        },
    )

    previous_repository = task_state.get_repository()
    try:
        task_state.configure_repository(repository, hydrate=False)
        _, continuation = prepare_initial_recovery(
            request=request,
            project={"source_path": str(source_root)},
            task_id="task-hash-continuation",
            target_languages=[{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
        )
    finally:
        task_state.configure_repository(previous_repository, hydrate=False)

    assert source_hash.call_count == 1
    assert continuation["source_snapshot_hash"] == "source-before"


def test_continuation_is_top_level_and_archives_superseded_task_after_lock(tmp_path):
    repository = _repository(tmp_path)
    repository.save_task({
        "task_id": "task-original",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "interrupted",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
    })
    previous_repository = task_state.get_repository()
    try:
        task_state.configure_repository(repository, hydrate=False)
        create_initial_translation_task(
            task_id="task-continuation",
            project={"name": "Visible project", "game_id": "victoria3"},
            request=SimpleNamespace(
                project_id="project-1",
                resume_from_task_id="task-original",
                idempotency_key="resume-once",
                translation_context_mode="project",
            ),
            context_resolution=SimpleNamespace(user_message="Queued", warning=None),
            provider_fields={},
            recovery={
                "run_id": "task-continuation",
                "resumed_from_task_id": "task-original",
            },
            resume_supported=True,
        )

        continuation = repository.get_task("task-continuation")
        original = repository.get_task("task-original")
        visible = repository.query_task_page(include_archived=False, include_children=False)

        assert continuation["parent_task_id"] is None
        assert continuation["workflow_context"]["resume_from_task_id"] == "task-original"
        assert continuation["title"] == "Resume translation for Visible project"
        assert original["archived_at"] is not None
        assert [task["task_id"] for task in visible["tasks"]] == ["task-continuation"]
        assert (
            TranslationRecoveryService(repository).latest_recovery_task("project-1")["task_id"]
            == "task-continuation"
        )
    finally:
        task_state.configure_repository(previous_repository, hydrate=False)


async def test_resume_idempotency_uses_recovery_lineage_for_top_level_task(monkeypatch):
    monkeypatch.setattr(translation_recovery, "checkpoint_resume_enabled", lambda: True)
    monkeypatch.setattr(
        task_state,
        "find_task_by_idempotency_key",
        lambda _key: {
            "task_id": "task-continuation",
            "status": "running",
            "parent_task_id": None,
            "recovery": {"resumed_from_task_id": "task-original"},
        },
    )

    result = await translation_recovery.resume_translation_task(
        "task-original",
        ResumeTranslationTaskRequest(idempotency_key="resume-once"),
        SimpleNamespace(),
    )

    assert result["task_id"] == "task-continuation"
    assert result["status"] == "running"


def test_continuation_rejects_provider_runtime_drift(tmp_path):
    repository = _repository(tmp_path)
    previous_repository = task_state.get_repository()
    task_state.configure_repository(repository, hydrate=False)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "localization.yml").write_text("l_english:\n", encoding="utf-8")
    request_payload = {
        "project_id": "project-runtime",
        "api_provider": "custom-profile",
        "model": "model-1",
        "target_lang_codes": ["zh-CN"],
        "use_resume": True,
        "resume_from_task_id": None,
    }
    request = SimpleNamespace(
        resume_from_task_id=None,
        project_id="project-runtime",
        model_dump=lambda mode=None: dict(request_payload),
    )
    runtime_a = SimpleNamespace(
        safe_metadata=lambda: {"config_fingerprint": "runtime-a"},
    )
    runtime_b = SimpleNamespace(
        safe_metadata=lambda: {"config_fingerprint": "runtime-b"},
    )
    try:
        _, recovery = prepare_initial_recovery(
            request=request,
            project={"source_path": str(source_root)},
            task_id="task-runtime",
            target_languages=[{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
            provider_runtime=runtime_a,
        )
        repository.save_task({
            "task_id": "task-runtime",
            "kind": "initial_translation",
            "project_id": "project-runtime",
            "status": "interrupted",
            "created_at": "2026-09-05T00:00:00Z",
            "updated_at": "2026-09-05T00:01:00Z",
            "recovery": recovery,
        })
        _checkpoint(recovery).mark_file_completed("localization.yml")
        request.resume_from_task_id = "task-runtime"
        request_payload["resume_from_task_id"] = "task-runtime"

        with pytest.raises(ValueError, match="configuration changed"):
            prepare_initial_recovery(
                request=request,
                project={"source_path": str(source_root)},
                task_id="task-runtime-resumed",
                target_languages=[{"code": "zh-CN", "folder_prefix": "zh-CN-"}],
                provider_runtime=runtime_b,
            )
    finally:
        task_state.configure_repository(previous_repository, hydrate=False)


@pytest.mark.parametrize("completed_count", [0, 1, 3])
def test_force_close_restores_exact_completed_units(tmp_path, completed_count):
    repository = _repository(tmp_path)
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "localization.yml").write_text("l_english:\n", encoding="utf-8")
    recovery = build_recovery_descriptor(
        task_id="task-running",
        project_id="project-1",
        source_root=str(source_root),
        output_dir=str(tmp_path / "output"),
        target_lang_codes=["zh-CN"],
        configuration={"project_id": "project-1"},
        snapshot_hash=source_tree_hash(str(source_root)),
    )
    repository.save_task({
        "task_id": "task-running",
        "kind": "initial_translation",
        "project_id": "project-1",
        "status": "processing",
        "created_at": "2026-08-31T00:00:00Z",
        "updated_at": "2026-08-31T00:01:00Z",
        "recovery": recovery,
    })
    assert repository.acquire_project_lock(task_id="task-running", project_id="project-1")
    checkpoint = _checkpoint(recovery)
    for index in range(completed_count):
        checkpoint.mark_file_completed(f"localisation/file-{index}.yml")

    lifecycle = TranslationTaskLifecycle(repository)
    lifecycle.recover_orphaned_tasks()
    lifecycle.recover_orphaned_tasks()
    projection = TranslationRecoveryService(repository).inspect("project-1")

    assert repository.get_task("task-running")["status"] == "interrupted"
    assert repository.get_project_lock("project-1") is None
    assert projection["checkpoint"]["completed_units"] == completed_count
    assert ("resume_task" in projection["allowed_actions"]) is (completed_count > 0)
