from scripts.core.services import initial_translation_task_service as task_service
from scripts.core.services.initial_translation_progress_service import LanguageRunState


class FakeCheckpoint:
    def __init__(self, completed=None):
        self.completed = set(completed or [])
        self.marked = []

    def is_file_completed(self, filename):
        return filename in self.completed

    def mark_file_completed(self, filename):
        self.marked.append(filename)


class FakeHandler:
    provider_name = "local"
    client = object()


def _build_iterator(
    files,
    checkpoint=None,
    progress_events=None,
    reference_resolver=None,
    reference_protected_entries=None,
    reference_run_metrics=None,
):
    return task_service.build_file_task_iterator(
        files,
        checkpoint or FakeCheckpoint(),
        source_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        target_lang={"code": "en", "key": "l_english"},
        game_profile={"id": "victoria3", "source_localization_folder": "localization"},
        mod_context="demo context",
        handler=FakeHandler(),
        output_folder_name="en-Test",
        mod_name="Test",
        proofreading_tracker=object(),
        progress_callback=(lambda *args, **kwargs: progress_events.append((args, kwargs))) if progress_events is not None else None,
        run_state=LanguageRunState(),
        total_batches=3,
        reference_resolver=reference_resolver,
        reference_protected_entries=reference_protected_entries,
        reference_run_metrics=reference_run_metrics,
    )


def test_build_file_task_iterator_skips_completed_files():
    files = [
        {
            "filename": "done.yml",
            "root": "root",
            "texts_to_translate": ["done"],
            "original_lines": [],
            "key_map": [],
            "is_custom_loc": False,
        }
    ]

    result = list(_build_iterator(files, checkpoint=FakeCheckpoint(completed={"done.yml"})))

    assert result == []


def test_build_file_task_iterator_handles_empty_files(monkeypatch):
    handled = []
    progress_events = []
    checkpoint = FakeCheckpoint()

    monkeypatch.setattr(
        task_service,
        "handle_empty_file",
        lambda *args, **kwargs: handled.append((args, kwargs)),
    )

    files = [
        {
            "filename": "empty.yml",
            "root": "root",
            "texts_to_translate": [],
            "original_lines": ["l_simp_chinese:"],
            "key_map": [],
            "is_custom_loc": False,
        }
    ]

    result = list(_build_iterator(files, checkpoint=checkpoint, progress_events=progress_events))

    assert result == []
    assert handled
    assert checkpoint.marked == ["empty.yml"]
    assert progress_events[0][1]["log_message"] == "Skipped empty file: empty.yml"


def test_build_file_task_iterator_wraps_file_data(monkeypatch):
    monkeypatch.setattr(task_service, "SOURCE_DIR", "J:/source")
    monkeypatch.setattr(task_service, "DEST_DIR", "J:/dest")

    files = [
        {
            "filename": "loc.yml",
            "root": "root",
            "texts_to_translate": ["你好"],
            "original_lines": ["l_simp_chinese:"],
            "key_map": [{"key_part": "demo.key"}],
            "is_custom_loc": False,
            "loc_root": "root/localization",
            "file_path": "localization/simp_chinese/loc.yml",
        }
    ]

    result = list(_build_iterator(files))

    assert len(result) == 1
    task = result[0]
    assert task.filename == "loc.yml"
    assert task.provider_name == "local"
    assert task.source_dir == "J:/source"
    assert task.dest_dir == "J:/dest"
    assert task.file_path == "localization/simp_chinese/loc.yml"


def test_build_file_task_iterator_removes_reference_hits_from_model_batch(monkeypatch):
    class Match:
        def __init__(self, translation=None):
            self.translation = translation
            self.hit = translation is not None

    class Resolver:
        def lookup(self, key, source_text, source_file=""):
            if key == "TRK:0" and source_text == "Turkana":
                return Match("图尔卡纳")
            return Match()

    files = [
        {
            "filename": "countries.yml",
            "root": "root",
            "texts_to_translate": ["Turkana", "Turkey"],
            "original_lines": ["l_english:"],
            "key_map": {
                0: {"key_part": "TRK:0"},
                1: {"key_part": "TRK:0"},
            },
            "is_custom_loc": False,
        }
    ]

    protected_entries = []
    run_metrics = {}
    task = list(_build_iterator(
        files,
        reference_resolver=Resolver(),
        reference_protected_entries=protected_entries,
        reference_run_metrics=run_metrics,
    ))[0]

    assert task.texts_to_translate == ["Turkey"]
    assert task.model_result_positions == [1]
    assert task.reference_translations == {0: "图尔卡纳"}
    assert task.all_source_texts == ["Turkana", "Turkey"]
    assert protected_entries == [{"source_file": "countries.yml", "key": "TRK:0"}]
    assert run_metrics == {"model_submitted": 1}
