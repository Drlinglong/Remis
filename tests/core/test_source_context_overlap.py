from pathlib import Path

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.services.incremental_preparation_service import IncrementalPreparationService
from scripts.core.services.initial_translation_task_service import build_file_task_iterator
from scripts.core.services.initial_translation_progress_service import LanguageRunState


def _file_task(texts, *, source_entries=None, translation_entry_indices=None):
    entries = source_entries or [
        {"key": f"key.{index}", "source": text}
        for index, text in enumerate(texts)
    ]
    return FileTask(
        filename="sample_l_english.yml",
        root="source",
        original_lines=[],
        texts_to_translate=list(texts),
        key_map={index: {"key_part": entry["key"]} for index, entry in enumerate(entries)},
        is_custom_loc=False,
        target_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        source_lang={"code": "en", "key": "l_english"},
        game_profile={"id": "victoria3"},
        mod_context="",
        provider_name="gemini",
        output_folder_name="output",
        source_dir="source",
        dest_dir="output",
        client=None,
        mod_name="Test",
        source_entries=entries,
        translation_entry_indices=translation_entry_indices or list(range(len(texts))),
    )


def test_source_context_covers_beginning_middle_and_end_batches_in_source_order():
    source_entries = [
        {"key": f"key.{index}", "source": f"Source {index}"}
        for index in range(6)
    ]
    processor = ParallelProcessor(max_workers=1, chunk_size_override=2, source_context_overlap=1)

    batches = processor._create_batch_tasks([
        _file_task([entry["source"] for entry in source_entries], source_entries=source_entries)
    ])

    assert [batch.texts for batch in batches] == [
        ["Source 0", "Source 1"],
        ["Source 2", "Source 3"],
        ["Source 4", "Source 5"],
    ]
    assert [[entry["key"] for entry in batch.context_entries] for batch in batches] == [
        ["key.2"],
        ["key.1", "key.4"],
        ["key.3"],
    ]


def test_zero_overlap_preserves_disabled_behavior():
    task = _file_task(["Source 0", "Source 1", "Source 2"])

    batches = ParallelProcessor(
        max_workers=1,
        chunk_size_override=1,
        source_context_overlap=0,
    )._create_batch_tasks([task])

    assert [batch.context_entries for batch in batches] == [[], [], []]
    assert [batch.texts for batch in batches] == [["Source 0"], ["Source 1"], ["Source 2"]]


def test_context_is_source_only_and_never_changes_output_mapping(monkeypatch):
    source_entries = [
        {"key": f"key.{index}", "source": f"Source {index}"}
        for index in range(5)
    ]
    task = _file_task(
        ["Source 1", "Source 3"],
        source_entries=source_entries,
        translation_entry_indices=[1, 3],
    )
    processor = ParallelProcessor(max_workers=1, chunk_size_override=2, source_context_overlap=1)
    monkeypatch.setattr("scripts.core.parallel_processor.glossary_manager.get_glossary_for_translation", lambda: None)

    seen = []

    def translate(batch):
        seen.append((list(batch.texts), list(batch.context_entries)))
        batch.translated_texts = [f"Translated {text}" for text in batch.texts]
        return batch

    results, _warnings = processor.process_files_parallel([task], translate)

    assert [entry["key"] for entry in seen[0][1]] == ["key.0", "key.2", "key.4"]
    assert all(set(entry) == {"key", "source"} for entry in seen[0][1])
    assert results[task.filename] == ["Translated Source 1", "Translated Source 3"]


def test_stream_processing_uses_the_same_source_context_contract(monkeypatch):
    task = _file_task(
        ["Source 0", "Source 1", "Source 2", "Source 3"],
    )
    processor = ParallelProcessor(max_workers=1, chunk_size_override=2, source_context_overlap=1)
    monkeypatch.setattr("scripts.core.parallel_processor.glossary_manager.get_glossary_for_translation", lambda: None)

    seen = []

    def translate(batch):
        seen.append([entry["key"] for entry in batch.context_entries])
        batch.translated_texts = list(batch.texts)
        return batch

    result = list(processor.process_files_stream(iter([task]), translate))

    assert seen == [["key.2"], ["key.1"]]
    assert result[0][1] == task.texts_to_translate
    assert result[0][3] is False


def test_initial_and_incremental_tasks_produce_identical_overlap_context():
    source_entries = [
        {"key": f"key.{index}:0", "source": f"Source {index}"}
        for index in range(5)
    ]
    initial_file_data = {
        "filename": "sample_l_english.yml",
        "root": "source",
        "original_lines": [],
        "texts_to_translate": [entry["source"] for entry in source_entries],
        "key_map": [{"key_part": entry["key"]} for entry in source_entries],
        "is_custom_loc": False,
        "file_path": "localization/english/sample_l_english.yml",
    }
    initial_task = next(build_file_task_iterator(
        [initial_file_data],
        checkpoint_manager=type("Checkpoint", (), {"is_file_completed": lambda _self, _name: False})(),
        source_lang={"code": "en", "key": "l_english"},
        target_lang={"code": "zh-CN", "key": "l_simp_chinese"},
        game_profile={"id": "victoria3"},
        mod_context="",
        handler=type("Handler", (), {"provider_name": "gemini", "client": None})(),
        output_folder_name="output",
        mod_name="Test",
        proofreading_tracker=None,
        progress_callback=None,
        run_state=LanguageRunState(),
        total_batches=3,
    ))

    class AllDirty:
        @staticmethod
        def classify_entry(_file_path, _key, _source, _history_index, target_lang_code=None):
            return "new", None

    incremental_result = IncrementalPreparationService().prepare_language_update(
        current_files_data=[{
            "filename": initial_file_data["filename"],
            "file_path": initial_file_data["file_path"],
            "root": "source",
            "original_lines": [],
            "parsed_entries": [
                (entry["key"], entry["source"], index + 1)
                for index, entry in enumerate(source_entries)
            ],
        }],
        history_index={},
        diff_service=AllDirty(),
        target_lang_info={"code": "zh-CN", "key": "l_simp_chinese"},
        source_lang_info={"code": "en", "key": "l_english"},
        game_profile={"id": "victoria3"},
        mod_context="",
        selected_provider="gemini",
        source_path="source",
        base_output_dir=Path("output"),
        total_targets=1,
    )
    incremental_task = incremental_result["file_tasks_for_ai"][0]

    processor = ParallelProcessor(max_workers=1, chunk_size_override=2, source_context_overlap=1)
    initial_batches = processor._create_batch_tasks([initial_task])
    incremental_batches = processor._create_batch_tasks([incremental_task])

    assert [batch.context_entries for batch in initial_batches] == [
        batch.context_entries for batch in incremental_batches
    ]


def test_prompt_labels_neighbor_entries_as_non_outputs():
    task = BatchTask(
        file_task=_file_task(["Current"]),
        batch_index=0,
        start_index=0,
        end_index=1,
        texts=["Current"],
        context_entries=[{"key": "neighbor.key:0", "source": "Neighbor source"}],
    )

    prompt = BaseApiHandler._build_source_context_prompt(task)

    assert "neighbor.key:0" in prompt
    assert "Neighbor source" in prompt
    assert "Do not translate them" in prompt
    assert "do not change the required output count" in prompt
