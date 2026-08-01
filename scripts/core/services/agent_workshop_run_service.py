"""Coordinate governed Agent Workshop repair batches and task projections."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from scripts.core.services.agent_workshop_task_projector import (
    WorkshopTaskProjector,
)


logger = logging.getLogger(__name__)


class WorkshopRunRequest(Protocol):
    """Request fields consumed by the run coordinator."""

    project_id: str
    api_provider: str
    api_model: str
    issues: list[dict[str, Any]]
    batch_size_limit: int | None
    concurrency_limit: int | None
    rpm_limit: int | None
    max_retries: int | None
    created_by: Any


BatchRequestFactory = Callable[[list[dict[str, Any]], int], Any]
BatchRunner = Callable[[Any], Awaitable[Any]]
Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class WorkshopRunConfig:
    """Normalized execution settings for one governed repair run."""

    batch_size: int
    concurrency: int
    rpm: int
    max_retries: int

    @classmethod
    def from_request(cls, request: WorkshopRunRequest) -> "WorkshopRunConfig":
        return cls(
            batch_size=max(1, min(request.batch_size_limit or 10, 50)),
            concurrency=max(1, min(request.concurrency_limit or 1, 5)),
            rpm=max(1, request.rpm_limit or 40),
            max_retries=max(1, min(request.max_retries or 3, 5)),
        )


@dataclass
class WorkshopRunStats:
    """Mutable counters protected by the coordinator stats lock."""

    completed: int = 0
    success_count: int = 0
    failed_count: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)


class AgentWorkshopRunCoordinator:
    """Run repair batches while projecting stable parent and child task state."""

    def __init__(
        self,
        *,
        task_id: str,
        request: WorkshopRunRequest,
        task_store: Any,
        batch_runner: BatchRunner,
        batch_request_factory: BatchRequestFactory,
        sleep: Sleep = asyncio.sleep,
        monotonic: Clock = time.monotonic,
        wall_time: Clock = time.time,
    ) -> None:
        self.task_id = task_id
        self.request = request
        self.batch_runner = batch_runner
        self.batch_request_factory = batch_request_factory
        self.sleep = sleep
        self.monotonic = monotonic
        self.wall_time = wall_time
        self.config = WorkshopRunConfig.from_request(request)
        self.batches = self._build_batches()
        self.total = len(request.issues)
        self.total_batches = len(self.batches)
        self.started_at = wall_time()
        self.queue: asyncio.Queue[tuple[int, list[dict[str, Any]]]] = asyncio.Queue()
        self.rate_lock = asyncio.Lock()
        self.stats_lock = asyncio.Lock()
        self.next_dispatch_at = 0.0
        self.stats = WorkshopRunStats()
        self.projector = WorkshopTaskProjector(
            task_store=task_store,
            task_id=task_id,
            project_id=request.project_id,
            created_by=request.created_by.model_dump(),
            total=self.total,
            total_batches=self.total_batches,
        )

    async def run(self) -> None:
        """Create task projections, execute workers, and persist one terminal state."""
        self._queue_child_tasks()
        self.projector.start_parent(
            concurrency=self.config.concurrency,
            rpm=self.config.rpm,
            max_retries=self.config.max_retries,
        )
        try:
            await asyncio.gather(
                *[
                    self._worker(index)
                    for index in range(1, self._worker_count() + 1)
                ]
            )
            self._complete_parent_task()
        except Exception as exc:
            logger.exception("Agent Workshop run failed")
            self._fail_parent_task(exc)

    def _build_batches(self) -> list[list[dict[str, Any]]]:
        return [
            self.request.issues[index:index + self.config.batch_size]
            for index in range(0, len(self.request.issues), self.config.batch_size)
        ]

    def _worker_count(self) -> int:
        return min(self.config.concurrency, max(self.total_batches, 1))

    def _queue_child_tasks(self) -> None:
        for batch_number, batch in enumerate(self.batches, start=1):
            self.projector.queue_child_task(batch_number, batch)
            self.queue.put_nowait((batch_number, batch))


    async def _wait_for_rate_limit(self) -> None:
        async with self.rate_lock:
            now = self.monotonic()
            wait_seconds = max(0.0, self.next_dispatch_at - now)
            self.next_dispatch_at = (
                max(now, self.next_dispatch_at) + (60 / self.config.rpm)
            )
        if wait_seconds > 0:
            await self.sleep(wait_seconds)

    async def _worker(self, worker_id: int) -> None:
        while True:
            try:
                batch_number, batch = self.queue.get_nowait()
            except asyncio.QueueEmpty:
                return
            await self._wait_for_rate_limit()
            self._start_child_task(worker_id, batch_number, batch)
            try:
                await self._execute_batch(batch_number, batch)
            except Exception as exc:
                await self._record_batch_failure(batch_number, batch, exc)
            finally:
                self.queue.task_done()

    def _start_child_task(
        self,
        worker_id: int,
        batch_number: int,
        batch: list[dict[str, Any]],
    ) -> None:
        self.projector.start_child(
            worker_id=worker_id,
            batch_number=batch_number,
            batch_size=len(batch),
            completed=self.stats.completed,
        )

    async def _execute_batch(
        self,
        batch_number: int,
        batch: list[dict[str, Any]],
    ) -> None:
        batch_request = self.batch_request_factory(batch, self.config.max_retries)
        response = await self.batch_runner(batch_request)
        batch_results = [item.model_dump() for item in response.results]
        batch_attempts = [item.model_dump() for item in response.attempts]
        batch_success = sum(
            1 for item in batch_results if item.get("status") == "SUCCESS"
        )
        batch_failed = len(batch_results) - batch_success
        async with self.stats_lock:
            self.stats.results.extend(batch_results)
            self.stats.attempts.extend(
                {"batch_number": batch_number, **attempt}
                for attempt in batch_attempts
            )
            self.stats.completed += len(batch)
            self.stats.success_count += batch_success
            self.stats.failed_count += batch_failed
            snapshot = self._stats_snapshot()
        self.projector.complete_child(
            batch_number=batch_number,
            batch_size=len(batch),
            batch_results=batch_results,
            batch_success=batch_success,
            batch_failed=batch_failed,
        )
        self.projector.record_batch_progress(
            batch_number=batch_number,
            batch_size=len(batch),
            batch_success=batch_success,
            completed=snapshot[0],
            success_count=snapshot[1],
            failed_count=snapshot[2],
        )

    def _stats_snapshot(self) -> tuple[int, int, int]:
        return (
            self.stats.completed,
            self.stats.success_count,
            self.stats.failed_count,
        )


    async def _record_batch_failure(
        self,
        batch_number: int,
        batch: list[dict[str, Any]],
        error: Exception,
    ) -> None:
        logger.exception(
            "Agent Workshop batch %s failed",
            batch_number,
            exc_info=error,
        )
        async with self.stats_lock:
            self.stats.completed += len(batch)
            self.stats.failed_count += len(batch)
            completed = self.stats.completed
            failed_count = self.stats.failed_count
        self.projector.fail_child(
            batch_number=batch_number,
            batch_size=len(batch),
            error=error,
            completed=completed,
            failed_count=failed_count,
        )

    def _complete_parent_task(self) -> None:
        self.projector.complete_parent(
            summary=self._parent_summary(),
            results=self.stats.results,
            attempts=self.stats.attempts,
            success_count=self.stats.success_count,
            failed_count=self.stats.failed_count,
        )

    def _parent_summary(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "completed": self.stats.completed,
            "successCount": self.stats.success_count,
            "failedCount": self.stats.failed_count,
            "durationMs": int((self.wall_time() - self.started_at) * 1000),
            "batchSize": self.config.batch_size,
            "totalBatches": self.total_batches,
            "results": self.stats.results,
            "attempts": self.stats.attempts,
            "maxRetries": self.config.max_retries,
        }

    def _fail_parent_task(self, error: Exception) -> None:
        self.projector.fail_parent(error)
