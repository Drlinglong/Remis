import logging
import os
import re
import sqlite3
from datetime import datetime, timezone


seed_logger = logging.getLogger("remis_init")
BUNDLED_MAIN_SEED_KEY = "main"
BUNDLED_MAIN_SEED_VERSION = 1


def _seed_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_seed_state_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bundled_seed_state (
            seed_key TEXT PRIMARY KEY,
            seed_version INTEGER NOT NULL,
            applied_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'applied',
            last_error TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_attempt_at TEXT
        )
        """
    )
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(bundled_seed_state)").fetchall()
    }
    for name, ddl in (
        ("status", "status TEXT NOT NULL DEFAULT 'applied'"),
        ("last_error", "last_error TEXT"),
        ("attempt_count", "attempt_count INTEGER NOT NULL DEFAULT 0"),
        ("last_attempt_at", "last_attempt_at TEXT"),
    ):
        if name not in columns:
            conn.execute(f"ALTER TABLE bundled_seed_state ADD COLUMN {ddl}")


def bundled_main_seed_applied(db_path: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            _ensure_seed_state_schema(conn)
            row = conn.execute(
                "SELECT seed_version, status FROM bundled_seed_state WHERE seed_key = ?",
                (BUNDLED_MAIN_SEED_KEY,),
            ).fetchone()
        return bool(
            row
            and row[0] >= BUNDLED_MAIN_SEED_VERSION
            and row[1] == "applied"
        )
    except (OSError, sqlite3.Error):
        return False


def _mark_seed_attempt(db_path: str) -> None:
    now = _seed_now()
    with sqlite3.connect(db_path) as conn:
        _ensure_seed_state_schema(conn)
        conn.execute(
            """
            INSERT INTO bundled_seed_state (
                seed_key, seed_version, applied_at, status, last_error,
                attempt_count, last_attempt_at
            ) VALUES (?, 0, ?, 'pending', NULL, 1, ?)
            ON CONFLICT(seed_key) DO UPDATE SET
                status = 'pending',
                last_error = NULL,
                attempt_count = bundled_seed_state.attempt_count + 1,
                last_attempt_at = excluded.last_attempt_at
            """,
            (BUNDLED_MAIN_SEED_KEY, now, now),
        )


def _mark_seed_failed(db_path: str, error: Exception) -> None:
    now = _seed_now()
    error_text = f"{type(error).__name__}: {error}"[:2000]
    with sqlite3.connect(db_path) as conn:
        _ensure_seed_state_schema(conn)
        conn.execute(
            """
            UPDATE bundled_seed_state
            SET status = 'failed', last_error = ?, last_attempt_at = ?
            WHERE seed_key = ?
            """,
            (error_text, now, BUNDLED_MAIN_SEED_KEY),
        )


def _mark_seed_applied(db_path: str) -> None:
    now = _seed_now()
    with sqlite3.connect(db_path) as conn:
        _ensure_seed_state_schema(conn)
        conn.execute(
            """
            UPDATE bundled_seed_state
            SET seed_version = ?, status = 'applied', last_error = NULL,
                applied_at = ?, last_attempt_at = ?
            WHERE seed_key = ?
            """,
            (BUNDLED_MAIN_SEED_VERSION, now, now, BUNDLED_MAIN_SEED_KEY),
        )


def _import_seed_inserts(
    conn: sqlite3.Connection,
    seed_path: str,
    allowed_tables: set[str],
) -> int:
    if not os.path.exists(seed_path):
        raise FileNotFoundError(f"Bundled seed file not found: {seed_path}")

    inserted = 0
    statement_lines: list[str] = []

    def flush_statement() -> None:
        nonlocal inserted
        if not statement_lines:
            return
        statement = "\n".join(statement_lines).strip()
        statement_lines.clear()
        if not statement.upper().startswith("INSERT INTO"):
            return
        match = re.match(
            r"INSERT INTO\s+([A-Za-z_][A-Za-z0-9_]*)",
            statement,
            re.IGNORECASE,
        )
        if not match or match.group(1) not in allowed_tables:
            return
        safe_statement = re.sub(
            r"^INSERT INTO",
            "INSERT OR IGNORE INTO",
            statement,
            flags=re.IGNORECASE,
        )
        conn.execute(safe_statement)
        inserted += 1

    with open(seed_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            statement_lines.append(raw_line.rstrip("\n"))
            if stripped.endswith(";"):
                flush_statement()
    flush_statement()
    return inserted


def seed_main_database(db_path: str, resource_dir: str) -> None:
    data_dir = os.path.join(resource_dir, "data")
    _mark_seed_attempt(db_path)
    try:
        with sqlite3.connect(db_path) as conn:
            main_count = _import_seed_inserts(
                conn,
                os.path.join(data_dir, "seed_data_main.sql"),
                {"glossaries", "entries"},
            )
            project_count = _import_seed_inserts(
                conn,
                os.path.join(data_dir, "seed_data_projects.sql"),
                {"projects", "project_files", "project_glossary_bindings"},
            )
        _mark_seed_applied(db_path)
        seed_logger.info(
            "[SEED] Imported %s main statements and %s project statements.",
            main_count,
            project_count,
        )
    except Exception as exc:
        try:
            _mark_seed_failed(db_path, exc)
        except Exception as state_error:
            seed_logger.error(
                "[SEED] Failed to record seed failure state: %s",
                state_error,
            )
        raise
