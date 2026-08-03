import time

import pytest

from scripts.core.services.context_parallel_execution_service import (
    DEFAULT_CLOUD_CONCURRENCY,
    ContextParallelResult,
    map_context_calls_ordered,
    resolve_context_concurrency,
)


@pytest.mark.parametrize(
    "provider_id",
    [
        "lm_studio",
        "ollama",
        "local",
        "vllm",
        "koboldcpp",
        "oobabooga",
        "text-generation-webui",
        "hunyuan",
    ],
)
def test_resolve_context_concurrency_serializes_local_providers(provider_id):
    assert resolve_context_concurrency(None, provider_id) == 1


@pytest.mark.parametrize("provider_id", ["openrouter", "openai", "deepseek", ""])
def test_resolve_context_concurrency_defaults_cloud_providers_to_five(provider_id):
    assert resolve_context_concurrency(None, provider_id) == DEFAULT_CLOUD_CONCURRENCY


@pytest.mark.parametrize("limit", [1, 3, 5, 10, 20, 50])
def test_resolve_context_concurrency_honors_supported_explicit_values(limit):
    assert resolve_context_concurrency(limit, "lm_studio") == limit


@pytest.mark.parametrize("limit", [0, -1, 51])
def test_resolve_context_concurrency_rejects_out_of_range_values(limit):
    with pytest.raises(ValueError, match="between 1 and 50"):
        resolve_context_concurrency(limit, "openrouter")


def test_ordered_parallel_map_preserves_input_order_and_reports_each_completion():
    completed = []

    def worker(value):
        time.sleep((4 - value) * 0.01)
        return value * 10

    results = map_context_calls_ordered(
        [1, 2, 3],
        worker,
        max_workers=3,
        on_completed=completed.append,
    )

    assert [result.index for result in results] == [0, 1, 2]
    assert [result.value for result in results] == [10, 20, 30]
    assert all(result.succeeded for result in results)
    assert sorted(result.index for result in completed) == [0, 1, 2]


def test_ordered_parallel_map_keeps_per_item_failures_for_the_caller():
    def worker(value):
        if value == "bad":
            raise RuntimeError("provider unavailable")
        return value.upper()

    results = map_context_calls_ordered(["first", "bad", "last"], worker, max_workers=3)

    assert [result.item for result in results] == ["first", "bad", "last"]
    assert results[0].value == "FIRST"
    assert isinstance(results[1].error, RuntimeError)
    assert str(results[1].error) == "provider unavailable"
    assert results[2].value == "LAST"
    assert [result.succeeded for result in results] == [True, False, True]


def test_ordered_parallel_map_works_serially_and_returns_empty_input():
    completed: list[ContextParallelResult[int, int]] = []

    results = map_context_calls_ordered(
        [1, 2], lambda value: value + 1, max_workers=1, on_completed=completed.append
    )

    assert [result.value for result in results] == [2, 3]
    assert [result.index for result in completed] == [0, 1]
    assert map_context_calls_ordered([], lambda value: value, max_workers=1) == []
