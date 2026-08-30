"""Concurrency policy and ordered execution helpers for context analysis.

Context analysis has independent extraction and synthesis calls separated by
workflow barriers.  This module deliberately knows nothing about tasks,
checkpoints, or provider clients: callers receive one result per input and can
persist each completed result before continuing to the next stage.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Optional, TypeVar


InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

LOCAL_SERIAL_PROVIDERS = frozenset(
    {
        "ollama",
        "lm_studio",
        "local",
        "vllm",
        "koboldcpp",
        "oobabooga",
        "text-generation-webui",
        "hunyuan",
    }
)
DEFAULT_CLOUD_CONCURRENCY = 5
MAX_CONTEXT_CONCURRENCY = 50


@dataclass(frozen=True)
class ContextParallelResult(Generic[InputT, OutputT]):
    """The outcome for one input item, retaining the original input position."""

    index: int
    item: InputT
    value: Optional[OutputT] = None
    error: Optional[BaseException] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def resolve_context_concurrency(
    concurrency_limit: Optional[int],
    selected_provider: Optional[str],
) -> int:
    """Resolve the user selection without silently overriding an explicit value."""

    if concurrency_limit is not None:
        resolved = int(concurrency_limit)
        if not 1 <= resolved <= MAX_CONTEXT_CONCURRENCY:
            raise ValueError(
                f"context concurrency must be between 1 and {MAX_CONTEXT_CONCURRENCY}"
            )
        return resolved

    provider_id = (selected_provider or "").strip().lower()
    if provider_id in LOCAL_SERIAL_PROVIDERS:
        return 1
    return DEFAULT_CLOUD_CONCURRENCY


def map_context_calls_ordered(
    items: Iterable[InputT],
    worker: Callable[[InputT], OutputT],
    *,
    max_workers: int,
    on_completed: Optional[Callable[[ContextParallelResult[InputT, OutputT]], None]] = None,
) -> list[ContextParallelResult[InputT, OutputT]]:
    """Run independent calls concurrently and return a complete, input-ordered set.

    Worker failures are captured per item.  This makes the returned list a
    natural barrier: the caller can checkpoint completed successes, surface all
    errors together, and decide whether a subsequent stage may start.
    """

    materialized_items = list(items)
    resolved_workers = _validate_worker_count(max_workers)
    if not materialized_items:
        return []
    if resolved_workers == 1:
        return _run_serially(materialized_items, worker, on_completed)
    return _run_concurrently(materialized_items, worker, resolved_workers, on_completed)


def _validate_worker_count(max_workers: int) -> int:
    resolved = int(max_workers)
    if not 1 <= resolved <= MAX_CONTEXT_CONCURRENCY:
        raise ValueError(
            f"context concurrency must be between 1 and {MAX_CONTEXT_CONCURRENCY}"
        )
    return resolved


def _run_serially(
    items: list[InputT],
    worker: Callable[[InputT], OutputT],
    on_completed: Optional[Callable[[ContextParallelResult[InputT, OutputT]], None]],
) -> list[ContextParallelResult[InputT, OutputT]]:
    results = []
    for index, item in enumerate(items):
        result = _execute_one(index, item, worker)
        _notify_completion(result, on_completed)
        results.append(result)
    return results


def _run_concurrently(
    items: list[InputT],
    worker: Callable[[InputT], OutputT],
    max_workers: int,
    on_completed: Optional[Callable[[ContextParallelResult[InputT, OutputT]], None]],
) -> list[ContextParallelResult[InputT, OutputT]]:
    results: list[Optional[ContextParallelResult[InputT, OutputT]]] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=min(max_workers, len(items))) as executor:
        futures = {
            executor.submit(_execute_one, index, item, worker): index
            for index, item in enumerate(items)
        }
        for future in as_completed(futures):
            result = future.result()
            results[result.index] = result
            _notify_completion(result, on_completed)
    return [result for result in results if result is not None]


def _execute_one(
    index: int,
    item: InputT,
    worker: Callable[[InputT], OutputT],
) -> ContextParallelResult[InputT, OutputT]:
    try:
        return ContextParallelResult(index=index, item=item, value=worker(item))
    except Exception as error:  # caller decides whether one failure is fatal
        return ContextParallelResult(index=index, item=item, error=error)


def _notify_completion(
    result: ContextParallelResult[InputT, OutputT],
    on_completed: Optional[Callable[[ContextParallelResult[InputT, OutputT]], None]],
) -> None:
    if on_completed is not None:
        on_completed(result)
