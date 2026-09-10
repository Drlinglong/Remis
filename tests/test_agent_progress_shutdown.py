import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts.core.services.agent_progress_service import project_agent_progress
from scripts.core.services.initial_translation_progress_service import LanguageRunState, emit_progress
from scripts.core.services.translation_progress_callback import build_translation_progress_callback
from scripts.core.services.backend_lifespan import backend_lifespan
from scripts.shared import task_state


def test_files_and_batches_remain_distinct_through_persistence_callback(monkeypatch):
    captured = {}
    def update(task_id, **kwargs):
        captured.update(kwargs)
    monkeypatch.setattr(task_state, "update_progress", update)
    callback = build_translation_progress_callback("fixture", use_resume=False)
    state = LanguageRunState(completed_files=1, total_files=2, completed_batches=4, successful_batches=4)
    emit_progress(callback, state, total_batches=5)
    projected = project_agent_progress({"progress": captured, **captured["fields"]}, "translation")
    assert projected["completed_files"] == 1
    assert projected["total_files"] == 2
    assert projected["current_batch"] == 4
    assert projected["total_batches"] == 5
    assert projected["file_count_scope"] == "current_language"


def test_legacy_batch_only_task_does_not_invent_file_counts():
    projected = project_agent_progress({"progress": {"current": 5, "total": 5, "current_batch": 5, "total_batches": 5}}, "translation")
    assert projected["completed_files"] is None
    assert projected["total_files"] is None
    assert projected["current_batch"] == 5


def test_resume_file_counts_come_from_completed_file_set():
    checkpoint = SimpleNamespace(read_enabled=True, completed_files={"a.yml", "b.yml"},
                                 progress={"completed_batches": 8}, metadata={})
    state = LanguageRunState.from_checkpoint(checkpoint, total_files=3)
    assert (state.completed_files, state.total_files, state.completed_batches) == (2, 3, 8)


@pytest.mark.asyncio
async def test_lifespan_closes_engine_even_on_application_error(monkeypatch):
    from scripts.core.db_manager import db_manager
    close = AsyncMock()
    monkeypatch.setattr(db_manager, "close_async_engine", close)
    with pytest.raises(RuntimeError):
        async with backend_lifespan(None):
            raise RuntimeError("fixture")
    close.assert_awaited_once()


def test_disposed_aiosqlite_pool_allows_process_to_exit(tmp_path):
    script = '''
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from scripts.core.db_manager import DatabaseConnectionManager
async def main():
    manager = object.__new__(DatabaseConnectionManager)
    manager._async_engine = create_async_engine("sqlite+aiosqlite:///" + __import__('sys').argv[1])
    async with manager._async_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
    await manager.close_async_engine()
    await manager.close_async_engine()
    assert not hasattr(manager, '_async_engine')
asyncio.run(main())
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path / "pool.sqlite")],
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
