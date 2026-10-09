"""A shared DB manager must serve workers with independent event loops."""

import subprocess
import sys
import textwrap


def test_async_database_sessions_cross_worker_event_loops(tmp_path):
    # A subprocess bounds regression hangs from SQLAlchemy first-connect locks.
    script = textwrap.dedent("""
        import asyncio
        import sys
        from concurrent.futures import ThreadPoolExecutor
        from sqlalchemy import text
        from scripts.core.db_manager import DatabaseConnectionManager

        manager = object.__new__(DatabaseConnectionManager)
        manager.db_path = sys.argv[1]

        async def query():
            async with manager.async_session_scope() as session:
                return (await session.execute(text("SELECT 42"))).scalar_one()

        def worker(_):
            return [asyncio.run(query()) for _ in range(3)]

        with ThreadPoolExecutor(max_workers=3) as executor:
            assert list(executor.map(worker, range(3))) == [[42] * 3] * 3
        async def check_shutdown():
            engine = manager.get_async_engine()
            assert manager.get_async_engine() is engine
            assert all(not loop.is_closed() for loop in manager._async_engines)
            await manager.close_async_engine()
            assert not manager._async_engines
            assert not hasattr(manager, "_async_engine")
            await manager.close_async_engine()
        asyncio.run(check_shutdown())
    """)
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path / "cross-loop.sqlite")],
        capture_output=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
