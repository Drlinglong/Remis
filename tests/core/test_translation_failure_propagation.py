import pytest

from scripts.core.base_handler import BaseApiHandler
from scripts.core.parallel_processor import ParallelProcessor, ProcessingCancelledError
from scripts.core.parallel_types import BatchTask, FileTask
from scripts.core.provider_errors import (
    ProviderFatalError,
    classify_provider_fatal_error,
    provider_failure_task_fields,
)


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


class FatalProviderResponse(RuntimeError):
    status_code = 401


class FatalHandler(BaseApiHandler):
    def __init__(self, provider_name: str):
        self.calls = 0
        super().__init__(provider_name)

    def initialize_client(self):
        return object()

    def _build_prompt(self, task: BatchTask) -> str:
        return "prompt"

    def _call_api(self, client, prompt: str) -> str:
        self.calls += 1
        raise FatalProviderResponse("authentication failed")


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


def test_generate_with_messages_preserves_provider_failure():
    handler = AlwaysFailHandler("test")

    with pytest.raises(RuntimeError, match="api unavailable"):
        handler.generate_with_messages(
            [
                {"role": "system", "content": "Return JSON."},
                {"role": "user", "content": "Analyze this text."},
            ],
            temperature=0.0,
        )


def test_translate_batch_aborts_immediately_for_fatal_provider_error():
    task = BatchTask(
        file_task=_file_task(),
        batch_index=0,
        start_index=0,
        end_index=1,
        texts=["Hello"],
    )
    handler = FatalHandler("test")

    with pytest.raises(ProviderFatalError, match="authentication failed"):
        handler.translate_batch(task)

    assert handler.calls == 1
    assert task.warnings == [{
        "type": "provider_fatal",
        "batch_num": 1,
        "attempt": 1,
        "provider": "test",
        "message": "authentication failed",
    }]


@pytest.mark.parametrize("status_code", [429, 500, 503])
def test_transient_provider_status_remains_retryable(status_code):
    error = RuntimeError("temporary provider failure")
    error.status_code = status_code

    assert classify_provider_fatal_error(error, provider="test") is None


def test_invalid_model_message_is_run_fatal_without_status_code():
    fatal = classify_provider_fatal_error(
        RuntimeError("The requested model is not available"),
        provider="test",
    )

    assert isinstance(fatal, ProviderFatalError)
    assert fatal.reason_code == "provider_invalid_model"
    assert provider_failure_task_fields(fatal) == {
        "attention_reason_code": "provider_invalid_model",
        "attention_reason": (
            "The selected model is invalid or unavailable. "
            "Select a loaded or supported model."
        ),
    }


@pytest.mark.parametrize(
    ("status_code", "message", "reason_code"),
    [
        (401, "request rejected", "provider_authentication_failed"),
        (403, "request rejected", "provider_forbidden"),
        (422, "invalid request payload", "provider_invalid_request"),
    ],
)
def test_fatal_provider_errors_have_stable_user_facing_reason_codes(
    status_code,
    message,
    reason_code,
):
    error = RuntimeError(message)
    error.status_code = status_code

    fatal = classify_provider_fatal_error(error, provider="test")

    assert fatal.reason_code == reason_code
    assert provider_failure_task_fields(fatal)["attention_reason_code"] == reason_code


def test_stream_processor_stops_queued_batches_after_provider_fatal_error():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    file_task.texts_to_translate = ["one", "two", "three", "four"]
    calls = []

    def fatal_translation(task: BatchTask) -> BatchTask:
        calls.append(task.batch_index)
        raise ProviderFatalError("invalid model", provider="test", status_code=404)

    with pytest.raises(ProviderFatalError, match="invalid model"):
        list(processor.process_files_stream(iter([file_task]), fatal_translation))

    assert calls == [0]


def test_stream_processor_discards_in_flight_result_after_cancellation():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    file_task.texts_to_translate = ["one", "two", "three"]
    calls = []
    cancellation = {"requested": False}

    def translation_that_finishes_after_cancel(task: BatchTask) -> BatchTask:
        calls.append(task.batch_index)
        cancellation["requested"] = True
        task.translated_texts = ["late result"]
        return task

    with pytest.raises(ProcessingCancelledError, match="cancelled by user"):
        list(processor.process_files_stream(
            iter([file_task]),
            translation_that_finishes_after_cancel,
            should_cancel=lambda: cancellation["requested"],
        ))

    assert calls == [0]


def test_parallel_processor_stops_queued_batches_after_provider_fatal_error():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    file_task.texts_to_translate = ["one", "two", "three", "four"]
    calls = []

    def fatal_translation(task: BatchTask) -> BatchTask:
        calls.append(task.batch_index)
        raise ProviderFatalError("invalid model", provider="test", status_code=404)

    with pytest.raises(ProviderFatalError, match="invalid model"):
        processor.process_files_parallel([file_task], fatal_translation)

    assert calls == [0]


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


def test_stream_processor_reports_successful_batch_after_processing():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    completed = []

    def successful_translation(task: BatchTask) -> BatchTask:
        task.translated_texts = ["你好"]
        return task

    results = list(
        processor.process_files_stream(
            iter([file_task]),
            successful_translation,
            batch_progress_callback=completed.append,
        )
    )

    assert len(completed) == 1
    assert completed[0].failed is False
    assert completed[0].fell_back_to_source is False
    assert results[0][3] is False


def test_stream_processor_reports_failed_batch_after_processing():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    completed = []

    def fallback_translation(task: BatchTask) -> BatchTask:
        task.fell_back_to_source = True
        task.translated_texts = task.texts
        return task

    results = list(
        processor.process_files_stream(
            iter([file_task]),
            fallback_translation,
            batch_progress_callback=completed.append,
        )
    )

    assert len(completed) == 1
    assert completed[0].fell_back_to_source is True
    assert results[0][3] is True


def test_parallel_processor_surfaces_local_connection_failure_message():
    processor = ParallelProcessor(max_workers=1, chunk_size_override=1)
    file_task = _file_task()
    connection_message = (
        "无法连接 LM Studio：Remis 正在访问 http://127.0.0.1:1234/v1。"
        "请检查本地服务是否已启动，并确认端口设置正确。"
    )

    def failed_translation(task: BatchTask) -> BatchTask:
        task.failed = True
        task.fell_back_to_source = True
        task.translated_texts = task.texts
        task.warnings.append({"type": "api_error", "message": connection_message})
        return task

    with pytest.raises(RuntimeError, match="无法连接 LM Studio") as exc_info:
        processor.process_files_parallel([file_task], failed_translation)

    assert connection_message in str(exc_info.value)


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
