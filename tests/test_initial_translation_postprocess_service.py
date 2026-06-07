import os

from scripts.core.services import initial_translation_postprocess_service as postprocess_service


class FakeTracker:
    def __init__(self):
        self.attached = False
        self.saved = False

    def save_proofreading_progress(self):
        self.saved = True


def test_run_post_processing_updates_progress_and_attaches_results(monkeypatch, tmp_path):
    import scripts.core.post_processing_manager as post_processing_module

    progress_events = []
    tracker = FakeTracker()

    class FakePostProcessingManager:
        def __init__(self, game_profile, output_folder_path, source_root):
            self.game_profile = game_profile
            self.output_folder_path = output_folder_path
            self.source_root = source_root

        def run_validation(self, target_lang, source_lang, dynamic_valid_tags=None):
            assert target_lang["code"] == "zh-CN"
            assert source_lang["code"] == "en"
            assert dynamic_valid_tags == ["custom_tag"]
            return True

        def get_validation_stats(self):
            return {"total_errors": 2, "total_warnings": 3}

        def attach_results_to_proofreading_tracker(self, proofreading_tracker):
            proofreading_tracker.attached = True

    monkeypatch.setattr(postprocess_service, "DEST_DIR", str(tmp_path / "dest"))
    monkeypatch.setattr(post_processing_module, "PostProcessingManager", FakePostProcessingManager)

    postprocess_service.run_post_processing(
        mod_name="MyMod",
        game_profile={"id": "vic3"},
        target_lang={"code": "zh-CN"},
        source_lang={"code": "en"},
        output_folder_name="zh-CN-MyMod",
        proofreading_tracker=tracker,
        update_progress_callback=lambda **payload: progress_events.append(payload),
        source_root=str(tmp_path / "source" / "MyMod"),
        dynamic_valid_tags=["custom_tag"],
    )

    assert tracker.attached is True
    assert progress_events == [
        {
            "log_message": "Validation completed. Found 5 issue(s): 2 error(s), 3 warning(s).",
            "format_issues_override": 5,
        }
    ]


def test_finalize_language_run_resolves_tags_and_saves_tracker(monkeypatch, tmp_path):
    tracker = FakeTracker()
    run_calls = []
    source_root = str(tmp_path / "source" / "MyMod")

    monkeypatch.setattr(postprocess_service, "SOURCE_DIR", str(tmp_path / "source"))
    monkeypatch.setattr(postprocess_service, "resolve_dynamic_valid_tags", lambda game_profile, root: ["tag_a"])
    monkeypatch.setattr(
        postprocess_service,
        "run_post_processing",
        lambda *args, **kwargs: run_calls.append((args, kwargs)),
    )

    dynamic_tags = postprocess_service.finalize_language_run(
        mod_name="MyMod",
        game_profile={"id": "vic3"},
        target_lang={"code": "zh-CN"},
        source_lang={"code": "en"},
        output_folder_name="zh-CN-MyMod",
        proofreading_tracker=tracker,
        update_progress_callback=None,
        override_path=source_root,
    )

    assert dynamic_tags == ["tag_a"]
    assert tracker.saved is True
    assert run_calls[0][1]["source_root"] == source_root
    assert run_calls[0][1]["dynamic_valid_tags"] == ["tag_a"]
    assert run_calls[0][0][0] == "MyMod"
    assert run_calls[0][0][4] == "zh-CN-MyMod"
