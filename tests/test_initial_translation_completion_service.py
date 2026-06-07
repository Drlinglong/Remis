from scripts.core.services import initial_translation_completion_service as completion_service


def test_process_metadata_for_run_uses_primary_language_in_batch(monkeypatch):
    calls = []

    monkeypatch.setattr(
        completion_service,
        "process_metadata_for_language",
        lambda *args: calls.append(args),
    )

    completion_service.process_metadata_for_run(
        is_batch_mode=True,
        mod_name="MyMod",
        handler="handler",
        source_lang={"code": "en"},
        primary_target_lang={"code": "en"},
        last_target_lang={"code": "zh-CN"},
        output_folder_name="Multilanguage-MyMod",
        mod_context="context",
        game_profile={"id": "vic3"},
    )

    assert calls[0][3] == {"code": "en"}


def test_process_metadata_for_run_uses_last_language_in_single_mode(monkeypatch):
    calls = []

    monkeypatch.setattr(
        completion_service,
        "process_metadata_for_language",
        lambda *args: calls.append(args),
    )

    completion_service.process_metadata_for_run(
        is_batch_mode=False,
        mod_name="MyMod",
        handler="handler",
        source_lang={"code": "en"},
        primary_target_lang={"code": "en"},
        last_target_lang={"code": "zh-CN"},
        output_folder_name="zh-CN-MyMod",
        mod_context="context",
        game_profile={"id": "vic3"},
    )

    assert calls[0][3] == {"code": "zh-CN"}


def test_clear_translation_checkpoints_clears_each_language(monkeypatch):
    cleared = []

    class FakeCheckpoint:
        def __init__(self, target_code):
            self.target_code = target_code

        def clear_checkpoint(self):
            cleared.append(self.target_code)

    def fake_build_checkpoint_manager(output_dir_path, selected_provider, model_name, source_lang, target_lang, use_resume):
        assert use_resume is True
        return FakeCheckpoint(target_lang["code"])

    monkeypatch.setattr(completion_service, "build_checkpoint_manager", fake_build_checkpoint_manager)

    completion_service.clear_translation_checkpoints(
        output_dir_path="out",
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        source_lang={"code": "en"},
        target_languages=[{"code": "zh-CN"}, {"code": "ja"}],
    )

    assert cleared == ["zh-CN", "ja"]


def test_finalize_workflow_run_runs_tail_steps(monkeypatch):
    calls = []

    monkeypatch.setattr(completion_service, "process_metadata_for_run", lambda *args: calls.append(("metadata", args)))
    monkeypatch.setattr(completion_service, "clear_translation_checkpoints", lambda *args: calls.append(("clear", args)))
    monkeypatch.setattr(completion_service, "sync_project_outputs", lambda *args: calls.append(("sync", args)))

    completion_service.finalize_workflow_run(
        is_batch_mode=False,
        mod_name="MyMod",
        handler="handler",
        source_lang={"code": "en"},
        primary_target_lang={"code": "zh-CN"},
        last_target_lang={"code": "zh-CN"},
        output_folder_name="zh-CN-MyMod",
        mod_context="context",
        game_profile={"id": "vic3"},
        output_dir_path="out",
        selected_provider="gemini",
        model_name="gemini-2.5-flash",
        target_languages=[{"code": "zh-CN"}],
        project_id="project-1",
    )

    assert [call[0] for call in calls] == ["metadata", "clear", "sync"]
    assert calls[2][1] == ("project-1", "out")
