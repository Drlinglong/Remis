"""Application-owned cleanup after ASGI requests and jobs have drained."""

from contextlib import asynccontextmanager
import asyncio


@asynccontextmanager
async def backend_lifespan(app):
    try:
        if app is not None:
            from scripts.core.services.workshop_publication_runtime import publication_runtime

            await asyncio.to_thread(publication_runtime().recover)
        yield
    finally:
        from scripts.core.db_manager import db_manager

        await db_manager.close_async_engine()
