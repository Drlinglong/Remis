import pytest

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import ParallelProcessor
from scripts.core.parallel_types import BatchTask, FileTask


def _file_task() -> FileTask:
    return FileTask(
        filename="example_l_english.yml",
        root=".",
        original_lines=[],
        texts_to_translate=["Hello"],
        key_map={},
        is_custom_loc=False,
        target_lang={"code": "zh-CN", "name": "Simplified Chinese"},
        source_lang={"code": "en", "name": "English"},
        game_profile={},
        mod_context="",
        provider_name="lm_studio",
        output_folder_name="out",
        source_dir=".",
        dest_dir=".",
        client=object(),
        mod_name="Example",
    )


class AlwaysFailHandler(BaseApiHandler):
    def initialize_client(self):
        return object()

    def _build_prompt(self, task: BatchTask) -> str:
        return "prompt"

    def _call_api(self, client, prompt: str) -> str:
        raise RuntimeError("api unavailable")


def test_translate_batch_marks_retry_exhaustion_as_failed():
    task = BatchTask(
        file_task=_file_task(),
        batch_index=0,
        start_index=0,
        end_index=1,
        texts=["Hello"],
    )

    result = AlwaysFailHandler("test").translate_batch(task)

    assert result.failed is True
    assert result.fell_back_to_source is True
    assert result.translated_texts == ["Hello"]
    assert result.warnings[-1]["type"] == "fallback_to_source"


def test_stream_processor_treats_source_fallback_as_file_failure():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()

    def fallback_translation(task: BatchTask) -> BatchTask:
        task.fell_back_to_source = True
        task.translated_texts = task.texts
        return task

    results = list(processor.process_files_stream(iter([file_task]), fallback_translation))

    assert len(results) == 1
    yielded_file_task, translated_texts, warnings, is_failed = results[0]
    assert yielded_file_task is file_task
    assert translated_texts == ["Hello"]
    assert warnings == []
    assert is_failed is True


def test_stream_processor_preserves_batch_warnings():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()

    def translation_with_warning(task: BatchTask) -> BatchTask:
        task.translated_texts = ["你好"]
        task.warnings.append({"type": "format_validation", "message": "placeholder mismatch"})
        return task

    results = list(processor.process_files_stream(iter([file_task]), translation_with_warning))

    assert len(results) == 1
    _, translated_texts, warnings, is_failed = results[0]
    assert translated_texts == ["你好"]
    assert warnings == [{"type": "format_validation", "message": "placeholder mismatch"}]
    assert is_failed is False
