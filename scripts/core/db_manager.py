import sqlite3
import threading
import logging
from typing import Optional
from scripts.app_settings import PROJECTS_DB_PATH

logger = logging.getLogger(__name__)

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
        return conn
