"""Application-owned cleanup after ASGI requests and jobs have drained."""

from contextlib import asynccontextmanager


@asynccontextmanager
async def backend_lifespan(app):
    try:
        yield
    finally:
        from scripts.core.db_manager import db_manager

        await db_manager.close_async_engine()
