import pytest

from scripts.core.services import initial_translation_language_service as language_service


class FakeHandler:
    def translate_batch(self, batch_task):
        return batch_task


class FakeFileTask:
    filename = "demo.yml"


class FakeProcessor:
    def __init__(self, max_workers, chunk_size_override):
        self.max_workers = max_workers
        self.chunk_size_override = chunk_size_override

    def process_files_stream(self, file_task_generator, translation_function):
        yield (FakeFileTask(), ["translated"], [], False)


class FailingProcessor(FakeProcessor):
    def process_files_stream(self, file_task_generator, translation_function):
        yield (FakeFileTask(), ["source"], [{"type": "api_error"}], True)


def _run_language(monkeypatch, calls, processor_cls=FakeProcessor):
    monkeypatch.setattr(language_service, "create_proofreading_tracker", lambda *args: "tracker")
    monkeypatch.setattr(language_service, "build_checkpoint_manager", lambda *args, **kwargs: "checkpoint")
    monkeypatch.setattr(language_service, "build_file_task_iterator", lambda *args, **kwargs: iter(["task"]))
    monkeypatch.setattr(language_service, "resolve_max_workers", lambda *args: 2)
    monkeypatch.setattr(language_service, "ParallelProcessor", processor_cls)
    monkeypatch.setattr(language_service, "temporary_rpm_limit", lambda rpm: _null_context(calls, "rpm"))
    monkeypatch.setattr(language_service, "progress_log_bridge", lambda logger: _null_context(calls, "progress_log"))
    monkeypatch.setattr(language_service, "log_batch_warnings", lambda *args: calls.append(("warnings", args)))
    monkeypatch.setattr(language_service, "finalize_translated_file", lambda *args: calls.append(("finalize_file", args)))
    monkeypatch.setattr(language_service, "finalize_language_run", lambda *args, **kwargs: calls.append(("postprocess", args)) or ["tag"])
    monkeypatch.setattr(language_service, "export_workshop_issues_for_language", lambda *args, **kwargs: calls.append(("export", args, kwargs)))
    monkeypatch.setattr(language_service, "run_embedded_workshop_for_language", lambda *args, **kwargs: calls.append(("workshop", args, kwargs)))

    language_service.run_language_translation(
        mod_name="Mod",
        source_lang={"code": "zh-CN"},
        target_lang={"code": "en", "name": "English"},
        game_profile={"id": "victoria3"},
        mod_context="context",
        handler=FakeHandler(),
        output_folder_name="en-Mod",
        output_dir_path="out",
        selected_provider="local",
        model_name="model",
        all_files_content=[{"filename": "demo.yml"}],
        total_batches=1,
        effective_chunk_size=30,
        progress_callback=None,
        project_id="project-1",
        version_id=9,
        override_path=None,
        use_resume=True,
        concurrency_limit=None,
        rpm_limit=40,
        batch_size_limit=None,
        embedded_workshop={"enabled": True},
    )


class _null_context:
    def __init__(self, calls, name):
        self.calls = calls
        self.name = name

    def __enter__(self):
        self.calls.append((self.name, "enter"))

    def __exit__(self, exc_type, exc, tb):
        self.calls.append((self.name, "exit"))
        return False


def test_run_language_translation_success_runs_tail_steps(monkeypatch):
    calls = []

    _run_language(monkeypatch, calls)

    names = [call[0] for call in calls]
    assert "finalize_file" in names
    assert "postprocess" in names
    assert "export" in names
    assert "workshop" in names


def test_run_language_translation_failure_raises_before_postprocess(monkeypatch):
    calls = []

    with pytest.raises(RuntimeError, match="Translation failed for 1 file"):
        _run_language(monkeypatch, calls, processor_cls=FailingProcessor)

    names = [call[0] for call in calls]
    assert "finalize_file" in names
    assert "warnings" in names
    assert "postprocess" not in names
    assert "workshop" not in names
