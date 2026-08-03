"""Project-scoped removal boundary for regenerable Mod Archive data."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class ContextArchiveBusyError(RuntimeError):
    """Raised when an analysis run still owns the project archive."""


class ContextArchiveIntegrityError(RuntimeError):
    """Raised when immutable-release guards are not present as expected."""


_RELEASE_DELETE_TRIGGERS = (
    "trg_context_releases_no_delete",
    "trg_context_release_aggregates_no_delete",
    "trg_context_release_syntheses_no_delete",
    "trg_context_release_delivery_no_delete",
    "trg_context_release_overrides_no_delete",
)


class ContextArchiveRepository:
    """Remove one project's derived archive while preserving the project and glossary."""

    def __init__(self, db_path: str):
        self.db_path = str(Path(db_path))
        self._lock = threading.RLock()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @staticmethod
    def _count(connection: sqlite3.Connection, query: str, project_id: str) -> int:
        return int(connection.execute(query, (project_id,)).fetchone()[0])

    def archive_counts(self, project_id: str) -> dict[str, int]:
        with self._lock, self._connect() as connection:
            return self._archive_counts(connection, project_id)

    def remove_project_archive(self, project_id: str) -> dict[str, Any]:
        """Purge derived context data under a transaction and restore immutability guards."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                active_runs = self._count(
                    connection,
                    "SELECT COUNT(*) FROM context_analysis_runs "
                    "WHERE project_id = ? AND status = 'running'",
                    project_id,
                )
                if active_runs:
                    raise ContextArchiveBusyError(
                        "A context analysis run is still active for this project"
                    )
                counts = self._archive_counts(connection, project_id)
                if not any(counts.values()):
                    connection.rollback()
                    return {"removed": False, "counts": counts}

                trigger_rows = connection.execute(
                    "SELECT name, sql FROM sqlite_master WHERE type = 'trigger' "
                    f"AND name IN ({','.join('?' for _ in _RELEASE_DELETE_TRIGGERS)})",
                    _RELEASE_DELETE_TRIGGERS,
                ).fetchall()
                if {row["name"] for row in trigger_rows} != set(_RELEASE_DELETE_TRIGGERS):
                    raise ContextArchiveIntegrityError(
                        "Published-release deletion guards are incomplete; removal was refused"
                    )
                for trigger_name in _RELEASE_DELETE_TRIGGERS:
                    connection.execute(f'DROP TRIGGER "{trigger_name}"')

                self._delete_project_rows(connection, project_id)

                for row in trigger_rows:
                    connection.execute(row["sql"])
                connection.commit()
                return {"removed": True, "counts": counts}
            except Exception:
                connection.rollback()
                raise

    def _archive_counts(
        self, connection: sqlite3.Connection, project_id: str
    ) -> dict[str, int]:
        release_filter = "SELECT release_id FROM context_releases WHERE project_id = ?"
        source_filter = "SELECT source_item_id FROM context_source_items WHERE project_id = ?"
        aggregate_filter = "SELECT aggregate_id FROM context_aggregates WHERE project_id = ?"
        run_filter = "SELECT run_id FROM context_analysis_runs WHERE project_id = ?"
        return {
            "releases": self._count(
                connection, "SELECT COUNT(*) FROM context_releases WHERE project_id = ?", project_id
            ),
            "drafts": self._count(
                connection, "SELECT COUNT(*) FROM context_drafts WHERE project_id = ?", project_id
            ),
            "source_items": self._count(
                connection, "SELECT COUNT(*) FROM context_source_items WHERE project_id = ?", project_id
            ),
            "contributions": self._count(
                connection,
                f"SELECT COUNT(*) FROM context_contributions WHERE source_item_id IN ({source_filter})",
                project_id,
            ),
            "aggregates": self._count(
                connection, "SELECT COUNT(*) FROM context_aggregates WHERE project_id = ?", project_id
            ),
            "syntheses": self._count(
                connection,
                f"SELECT COUNT(*) FROM context_release_syntheses WHERE release_id IN ({release_filter})",
                project_id,
            ),
            "delivery_memberships": self._count(
                connection,
                f"SELECT COUNT(*) FROM context_release_delivery_memberships "
                f"WHERE release_id IN ({release_filter})",
                project_id,
            ),
            "analysis_runs": self._count(
                connection, "SELECT COUNT(*) FROM context_analysis_runs WHERE project_id = ?", project_id
            ),
            "analysis_batches": self._count(
                connection,
                f"SELECT COUNT(*) FROM context_analysis_batches WHERE run_id IN ({run_filter})",
                project_id,
            ),
            "aggregate_links": self._count(
                connection,
                f"SELECT COUNT(*) FROM context_aggregate_contributions "
                f"WHERE aggregate_id IN ({aggregate_filter})",
                project_id,
            ),
        }

    @staticmethod
    def _delete_project_rows(connection: sqlite3.Connection, project_id: str) -> None:
        release_filter = "SELECT release_id FROM context_releases WHERE project_id = ?"
        aggregate_filter = "SELECT aggregate_id FROM context_aggregates WHERE project_id = ?"
        source_filter = "SELECT source_item_id FROM context_source_items WHERE project_id = ?"
        connection.execute("DELETE FROM context_drafts WHERE project_id = ?", (project_id,))
        for table in (
            "context_release_overrides",
            "context_release_delivery_memberships",
            "context_release_syntheses",
            "context_release_aggregates",
        ):
            connection.execute(
                f"DELETE FROM {table} WHERE release_id IN ({release_filter})", (project_id,)
            )
        connection.execute("DELETE FROM context_releases WHERE project_id = ?", (project_id,))
        connection.execute(
            f"DELETE FROM context_aggregate_contributions "
            f"WHERE aggregate_id IN ({aggregate_filter})",
            (project_id,),
        )
        connection.execute("DELETE FROM context_aggregates WHERE project_id = ?", (project_id,))
        connection.execute(
            f"DELETE FROM context_contributions WHERE source_item_id IN ({source_filter})",
            (project_id,),
        )
        connection.execute("DELETE FROM context_source_items WHERE project_id = ?", (project_id,))
        connection.execute("DELETE FROM context_analysis_runs WHERE project_id = ?", (project_id,))
