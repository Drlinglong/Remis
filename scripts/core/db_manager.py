import asyncio
import sqlite3
import weakref
import threading
import logging
from typing import Optional
from contextlib import asynccontextmanager
from scripts.app_settings import PROJECTS_DB_PATH

logger = logging.getLogger(__name__)


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record=None):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


class DatabaseConnectionManager:
    """
    Singleton Manager for SQLite connections.
    Ensures WAL mode is enabled and provides consistent connection parameters (timeout, row_factory).
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(DatabaseConnectionManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: Optional[str] = None):
        if self._initialized:
            return
            
        self.db_path = db_path or PROJECTS_DB_PATH
        self._ensure_wal_mode()
        self._initialized = True
        logger.info(f"DatabaseConnectionManager initialized for {self.db_path}")

    def _ensure_wal_mode(self):
        """Enables Write-Ahead Logging (WAL) for better concurrency."""
        try:
            conn = sqlite3.connect(self.db_path)
            # WAL allows simultaneous readers and writers
            conn.execute("PRAGMA journal_mode=WAL;")
            # NORMAL synchronous is faster and safe enough for typical desktop usage
            conn.execute("PRAGMA synchronous=NORMAL;") 
            conn.close()
        except Exception as e:
            logger.error(f"Failed to enable WAL mode: {e}")

    def get_connection(self) -> sqlite3.Connection:
        """
        Returns a configured SQLite connection.
        timeout=30s (default is 5s) to reduce 'database is locked' errors during heavy concurrent access.
        """
        conn = sqlite3.connect(
            self.db_path, 
            timeout=30.0, 
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        _enable_sqlite_foreign_keys(conn)
        return conn

    # --- Async Support (SQLModel) ---
    def get_async_engine(self):
        """Return an engine scoped to the caller's event loop and database."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool
        from sqlalchemy import event

        loop = asyncio.get_running_loop()
        with self._lock:
            if not hasattr(self, "_async_engines"):
                self._async_engines = weakref.WeakKeyDictionary()
            for old_loop, (_, old_engine) in list(self._async_engines.items()):
                if old_loop.is_closed():
                    # NullPool retains no connections; disposal here does not
                    # require I/O on the closed loop.
                    old_engine.sync_engine.dispose()
                    del self._async_engines[old_loop]
            cached = self._async_engines.get(loop)
            if cached is None or cached[0] != self.db_path:
                path = self.db_path.replace("\\", "/")
                # NullPool prevents connection reuse across loops. Engines also
                # need loop isolation: SQLAlchemy's first-connect initialization
                # uses an asyncio lock, even when the pool is NullPool.
                engine = create_async_engine(
                    f"sqlite+aiosqlite:///{path}", echo=False, future=True,
                    poolclass=NullPool,
                )
                event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
                self._async_engines[loop] = (self.db_path, engine)
            else:
                engine = cached[1]
            self._async_engine = engine
            return engine

    async def get_async_session(self):
        """
        Generator for AsyncSession.
        Usage: 
            async for session in db_manager.get_async_session():
                ...
        """
        from sqlmodel.ext.asyncio.session import AsyncSession
        from sqlalchemy.orm import sessionmaker

        engine = self.get_async_engine()
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            yield session

    async def close_async_engine(self):
        """Dispose all loop-scoped engines when the backend shuts down."""
        with self._lock:
            engines = {entry[1] for entry in getattr(self, "_async_engines", {}).values()}
            engine = getattr(self, "_async_engine", None)
            if engine is not None:
                engines.add(engine)
                del self._async_engine
            if hasattr(self, "_async_engines"):
                self._async_engines.clear()
        for engine in engines:
            await engine.dispose()

    @asynccontextmanager
    async def async_session_scope(self):
        """
        异步事务上下文管理器。
        """
        from sqlmodel.ext.asyncio.session import AsyncSession
        from sqlalchemy.orm import sessionmaker

        engine = self.get_async_engine()
        async_session = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
        
        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

# Singleton Instance
db_manager = DatabaseConnectionManager()
