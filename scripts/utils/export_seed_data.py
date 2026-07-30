"""Export deterministic release seed SQL from repository-reviewed assets.

Release builds must never read the developer's live Remis databases. The source
database passed to this script is expected to be a checked-in asset containing
exactly the three approved demo projects.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE_DB = PROJECT_ROOT / "assets" / "skeleton.sqlite"
DEFAULT_CACHE_DB = PROJECT_ROOT / "assets" / "mods_cache_skeleton.sqlite"
DEFAULT_MAIN_OUTPUT = PROJECT_ROOT / "data" / "seed_data_main.sql"
DEFAULT_PROJECTS_OUTPUT = PROJECT_ROOT / "data" / "seed_data_projects.sql"

DEMO_PROJECTS = (
    (
        "6049331a-433d-4d09-9205-165c3aad6010",
        "Project Remis - Demo Mod - Stellaris",
    ),
    (
        "a525f596-6c71-43fe-ade2-52c9205a2720",
        "蕾姆丝计划 - 演示Mod - 维多利亚3",
    ),
    (
        "ae507ae2-2a08-44e3-9c3d-caa4445911f2",
        "Project Remis - Demo Mod -EU5",
    ),
)
DEMO_PROJECTS_BY_ID = dict(DEMO_PROJECTS)
DEMO_PROJECT_IDS = tuple(DEMO_PROJECTS_BY_ID)
DEMO_PROJECT_NAMES = frozenset(DEMO_PROJECTS_BY_ID.values())

MAIN_SEED_TABLES = ("glossaries", "entries")
PROJECT_SEED_TABLES = (
    "projects",
    "project_files",
    "project_glossary_bindings",
)
REQUIRED_SOURCE_TABLES = frozenset((*MAIN_SEED_TABLES, *PROJECT_SEED_TABLES))
ALLOWED_PATH_PREFIXES = (
    "{{BUNDLED_DEMO_ROOT}}/",
    "{{BUNDLED_TRANSLATION_ROOT}}/",
)
WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def _connect_existing(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(f"Release seed database not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _validate_demo_identity(
    actual_rows: Iterable[sqlite3.Row | Sequence[str]],
    *,
    label: str,
) -> None:
    actual = {str(row[0]): str(row[1]) for row in actual_rows}
    if actual != DEMO_PROJECTS_BY_ID:
        expected_text = ", ".join(
            f"{project_id}={name}" for project_id, name in DEMO_PROJECTS
        )
        actual_text = ", ".join(
            f"{project_id}={name}" for project_id, name in sorted(actual.items())
        )
        raise ValueError(
            f"{label} must contain exactly the three approved demo projects. "
            f"Expected [{expected_text}], found [{actual_text or 'none'}]."
        )


def validate_release_assets(source_db: Path, cache_db: Path) -> None:
    """Fail closed unless both packaged databases contain only the approved demos."""
    with _connect_existing(source_db) as connection:
        missing = REQUIRED_SOURCE_TABLES - _table_names(connection)
        if missing:
            raise ValueError(
                "Release seed database is missing required tables: "
                + ", ".join(sorted(missing))
            )
        _validate_demo_identity(
            connection.execute(
                "SELECT project_id, name FROM projects ORDER BY project_id"
            ).fetchall(),
            label="Release seed database",
        )
        foreign_key_errors = [
            error
            for table_name in REQUIRED_SOURCE_TABLES
            for error in connection.execute(
                f'PRAGMA foreign_key_check("{table_name}")'
            ).fetchall()
        ]
        if foreign_key_errors:
            raise ValueError(
                "Release seed tables have foreign-key violations."
            )

    with _connect_existing(cache_db) as connection:
        if "mods" not in _table_names(connection):
            raise ValueError("Release cache database is missing the mods table.")
        cache_rows = connection.execute(
            "SELECT CAST(mod_id AS TEXT), name FROM mods ORDER BY name"
        ).fetchall()
        actual_names = {str(row[1]) for row in cache_rows}
        if actual_names != DEMO_PROJECT_NAMES or len(cache_rows) != len(DEMO_PROJECTS):
            raise ValueError(
                "Release cache database must contain exactly the three approved "
                f"demo mods; found {sorted(actual_names)}."
            )
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise ValueError("Release cache database has foreign-key violations.")


def _column_names(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    ]


def _sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bytes):
        return f"X'{value.hex()}'"
    if isinstance(value, str):
        return "'" + value.replace("'", "''") + "'"
    return str(value)


def _insert_statement(
    table_name: str,
    column_names: Sequence[str],
    values: Sequence[object],
) -> str:
    columns = ", ".join(column_names)
    literals = ", ".join(_sql_literal(value) for value in values)
    return f"INSERT INTO {table_name} ({columns}) VALUES ({literals});"


def sanitize_release_path(value: object) -> object:
    if not isinstance(value, str) or not value:
        return value

    path = value.replace("\\", "/")
    path = path.replace(
        "{{PROJECT_ROOT}}/my_translation/",
        "{{BUNDLED_TRANSLATION_ROOT}}/",
    )
    if "/source_mod/" in path:
        path = "{{BUNDLED_DEMO_ROOT}}/" + path.split("/source_mod/", 1)[1]
    elif "/demos/" in path:
        path = "{{BUNDLED_DEMO_ROOT}}/" + path.split("/demos/", 1)[1]
    elif "/my_translation/" in path:
        path = "{{BUNDLED_TRANSLATION_ROOT}}/" + path.split(
            "/my_translation/", 1
        )[1]

    if path.startswith(ALLOWED_PATH_PREFIXES):
        return path
    if WINDOWS_ABSOLUTE_PATH.match(path) or path.startswith(("/", "//")):
        raise ValueError(f"Unmapped absolute path in release seed: {value}")
    if "{{" in path or "}}" in path:
        raise ValueError(f"Unsupported placeholder in release seed path: {value}")
    return path


def sanitize_release_metadata(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: sanitize_release_metadata(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_release_metadata(item) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        is_path = (
            WINDOWS_ABSOLUTE_PATH.match(value)
            or normalized.startswith(("/", "//", "{{PROJECT_ROOT}}/"))
        )
        if is_path:
            return sanitize_release_path(value)
    return value


def sanitize_raw_metadata(value: object) -> object:
    if not isinstance(value, str) or not value:
        return value
    try:
        metadata = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid raw_metadata JSON in release seed.") from exc
    return json.dumps(
        sanitize_release_metadata(metadata),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _write_seed(
    output_path: Path,
    *,
    title: str,
    statements: Iterable[str],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"-- {title}\n")
        handle.write("BEGIN TRANSACTION;\n\n")
        for statement in statements:
            handle.write(statement)
            handle.write("\n")
        handle.write("\nCOMMIT;\n")


def _main_seed_statements(connection: sqlite3.Connection) -> list[str]:
    statements: list[str] = []
    for table_name in MAIN_SEED_TABLES:
        columns = _column_names(connection, table_name)
        rows = connection.execute(
            f'SELECT * FROM "{table_name}" ORDER BY rowid'
        ).fetchall()
        for row in rows:
            values = list(row)
            if "raw_metadata" in columns:
                index = columns.index("raw_metadata")
                values[index] = sanitize_raw_metadata(values[index])
            statements.append(_insert_statement(table_name, columns, values))
    return statements


def _project_seed_statements(connection: sqlite3.Connection) -> list[str]:
    statements: list[str] = []
    placeholders = ", ".join("?" for _ in DEMO_PROJECT_IDS)
    order_by = {
        "projects": "project_id",
        "project_files": "project_id, file_id",
        "project_glossary_bindings": "project_id, glossary_id",
    }

    for table_name in PROJECT_SEED_TABLES:
        columns = _column_names(connection, table_name)
        rows = connection.execute(
            f'SELECT * FROM "{table_name}" '
            f"WHERE project_id IN ({placeholders}) ORDER BY {order_by[table_name]}",
            DEMO_PROJECT_IDS,
        ).fetchall()
        for row in rows:
            values = list(row)
            for path_column in ("source_path", "target_path", "file_path"):
                if path_column in columns:
                    index = columns.index(path_column)
                    values[index] = sanitize_release_path(values[index])
            statements.append(_insert_statement(table_name, columns, values))
    return statements


def export_release_seeds(
    *,
    source_db: Path,
    cache_db: Path,
    main_output: Path,
    projects_output: Path,
) -> tuple[int, int]:
    validate_release_assets(source_db, cache_db)
    with _connect_existing(source_db) as connection:
        main_statements = _main_seed_statements(connection)
        project_statements = _project_seed_statements(connection)

    _write_seed(
        main_output,
        title="Remis Main DB Seed Data (reviewed release asset)",
        statements=main_statements,
    )
    _write_seed(
        projects_output,
        title="Remis Demo Projects Seed Data (three-project allowlist)",
        statements=project_statements,
    )
    return len(main_statements), len(project_statements)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export reviewed Remis release seed data."
    )
    parser.add_argument("--source-db", type=Path, default=DEFAULT_SOURCE_DB)
    parser.add_argument("--cache-db", type=Path, default=DEFAULT_CACHE_DB)
    parser.add_argument("--main-output", type=Path, default=DEFAULT_MAIN_OUTPUT)
    parser.add_argument(
        "--projects-output",
        type=Path,
        default=DEFAULT_PROJECTS_OUTPUT,
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    main_count, project_count = export_release_seeds(
        source_db=args.source_db.resolve(),
        cache_db=args.cache_db.resolve(),
        main_output=args.main_output.resolve(),
        projects_output=args.projects_output.resolve(),
    )
    print(
        "Release seed export complete: "
        f"{main_count} glossary statements, "
        f"{project_count} demo-project statements."
    )


if __name__ == "__main__":
    main()
