"""Restart-safe status constraints for nullable legacy SQLite schemas."""

import sqlite3

STATUS_CONTRACTS = {
    "projects": ("active", ("active", "archived", "deleted")),
    "project_files": ("todo", ("todo", "in_progress", "proofreading", "paused", "done")),
    "project_watches": ("never_scanned", ("never_scanned", "baseline", "clean", "changed", "no_localization", "error")),
}


def enforce_nonnull_status_contracts(db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        for table, (default, statuses) in STATUS_CONTRACTS.items():
            for event in ("insert", "update"):
                connection.execute(f"DROP TRIGGER IF EXISTS trg_{table}_status_{event}")
            # Only normalize known legacy states. Preserve unrelated invalid rows
            # for human review instead of silently rewriting their semantics.
            if table == "project_files":
                connection.execute("UPDATE project_files SET status='done' WHERE status='translated'")
            connection.execute(f"UPDATE {table} SET status=? WHERE status IS NULL", (default,))
            values = ", ".join(repr(status) for status in statuses)
            for event, operation in (("insert", "INSERT"), ("update", "UPDATE OF status")):
                connection.execute(f"""
                    CREATE TRIGGER trg_{table}_status_{event}
                    BEFORE {operation} ON {table}
                    FOR EACH ROW WHEN NEW.status IS NULL OR NEW.status NOT IN ({values})
                    BEGIN
                        SELECT RAISE(ABORT, 'invalid {table}.status');
                    END
                """)
        connection.commit()
