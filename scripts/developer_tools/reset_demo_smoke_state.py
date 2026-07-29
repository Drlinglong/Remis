"""Reset Remis demo projects into deterministic smoke-test states.

This tool is intentionally limited to the three official demo project IDs and
the repository-owned smoke fixtures. It is not a general database reset.
Run without ``--yes`` to preview the exact scopes and paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
VIC3_PROJECT_ID = "a525f596-6c71-43fe-ade2-52c9205a2720"
STELLARIS_PROJECT_ID = "6049331a-433d-4d09-9205-165c3aad6010"
EU5_PROJECT_ID = "ae507ae2-2a08-44e3-9c3d-caa4445911f2"
SCOPES = ("initial", "incremental", "workshop", "neologism")
TERMINAL_TASK_STATUSES = (
    "completed",
    "complete",
    "success",
    "failed",
    "partial_failed",
    "cancelled",
    "canceled",
    "interrupted",
)
WORKSHOP_FIXTURE_RELATIVE = Path(
    "tests/fixtures/demo_smoke/agent_workshop_broken"
)
VIC3_BASE_RELATIVE = Path("source_mod/Test_Project_Remis_Vic3")
VIC3_UPDATE_RELATIVE = Path(
    "source_mod/Test_Project_Remis_Vic3_Incremental_Frozen"
)


class ResetSafetyError(RuntimeError):
    """Raised when a reset target is ambiguous or outside the demo boundary."""


@dataclass(frozen=True)
class ResetPaths:
    repo_root: Path
    fixture_repo_root: Path
    app_data_dir: Path
    main_db: Path
    archive_db: Path
    archive_seed_db: Path
    backup_root: Path


def _default_app_data_dir() -> Path:
    roaming = os.environ.get("APPDATA")
    if roaming:
        return Path(roaming) / "RemisModFactoryDev"
    return Path.home() / ".remismodfactorydev"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _require_within(path: Path, root: Path, *, label: str) -> None:
    if not _is_relative_to(path, root):
        raise ResetSafetyError(
            f"{label} is outside the allowed root: {path} (root: {root})"
        )


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _json_dict(raw: object) -> dict:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _candidate_cache_name(project_id: str) -> str:
    return hashlib.sha256(project_id.encode("utf-8")).hexdigest() + ".json"


def _backup_sqlite(source_path: Path, destination_path: Path) -> None:
    """Create a transactionally consistent backup, including WAL contents."""
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as source:
        with sqlite3.connect(destination_path) as destination:
            source.backup(destination)


def discover_worktree_roots(repo_root: Path) -> list[Path]:
    roots: list[Path] = []
    try:
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        roots.extend(
            Path(line.removeprefix("worktree ").strip())
            for line in result.stdout.splitlines()
            if line.startswith("worktree ")
        )
    except (OSError, subprocess.SubprocessError):
        pass
    if repo_root not in roots:
        roots.append(repo_root)
    return list(dict.fromkeys(path.resolve() for path in roots))


def select_fixture_repo_root(repo_root: Path, worktrees: Sequence[Path]) -> Path:
    primary = next(
        (
            root
            for root in worktrees
            if (root / ".git").is_dir()
            and (root / VIC3_BASE_RELATIVE).is_dir()
            and (root / VIC3_UPDATE_RELATIVE).is_dir()
        ),
        None,
    )
    return (primary or repo_root).resolve()


class DemoSmokeReset:
    def __init__(
        self,
        paths: ResetPaths,
        scopes: Iterable[str],
        *,
        worktree_roots: Sequence[Path] | None = None,
        backend_port: int = 1453,
    ):
        self.paths = paths
        self.scopes = tuple(dict.fromkeys(scopes))
        self.backend_port = backend_port
        self.worktree_roots = list(
            worktree_roots
            if worktree_roots is not None
            else discover_worktree_roots(paths.repo_root)
        )
        unknown = set(self.scopes) - set(SCOPES)
        if unknown:
            raise ResetSafetyError(
                "Unsupported reset scope(s): " + ", ".join(sorted(unknown))
            )

    def preview(self) -> list[str]:
        actions = [
            f"backup SQLite databases to {self.paths.backup_root}",
            "archive terminal demo tasks (task logs remain recoverable)",
        ]
        if "initial" in self.scopes:
            actions.extend(
                [
                    "clear the EU5 demo translation output directory",
                    "clear archived EU5 translated results while preserving source data",
                ]
            )
        if "incremental" in self.scopes:
            actions.extend(
                [
                    f"restore {VIC3_BASE_RELATIVE} and {VIC3_UPDATE_RELATIVE}",
                    "restore the Vic3 archive to the packaged pre-update baseline",
                    "recreate the Vic3 baseline English translation file",
                    "remove registered and generated Vic3 incremental outputs",
                ]
            )
        if "workshop" in self.scopes:
            actions.extend(
                [
                    "restore the deterministic broken Agent Workshop fixture",
                    "register and index that fixture on the Stellaris demo project",
                ]
            )
        if "neologism" in self.scopes:
            actions.extend(
                [
                    "remove Stellaris demo candidate caches from all worktrees",
                    "delete only the Stellaris demo-owned project glossary",
                ]
            )
        return actions

    def backend_is_listening(self) -> bool:
        try:
            with socket.create_connection(
                ("127.0.0.1", self.backend_port),
                timeout=0.5,
            ):
                return True
        except OSError:
            return False

    def validate(self, *, allow_running_backend: bool = False) -> None:
        if self.backend_is_listening() and not allow_running_backend:
            raise ResetSafetyError(
                f"Remis backend is listening on 127.0.0.1:{self.backend_port}. "
                "Close the development app before applying the fixture reset."
            )
        required_databases = [
            (self.paths.main_db, "main database"),
            (self.paths.archive_db, "archive database"),
        ]
        if "incremental" in self.scopes:
            required_databases.append(
                (self.paths.archive_seed_db, "archive seed database")
            )
        for path, label in required_databases:
            if not path.is_file():
                raise ResetSafetyError(f"Missing {label}: {path}")
        if "incremental" in self.scopes:
            for relative in (VIC3_BASE_RELATIVE, VIC3_UPDATE_RELATIVE):
                source = self.paths.fixture_repo_root / relative
                if not source.is_dir():
                    raise ResetSafetyError(
                        f"Missing incremental fixture: {source}"
                    )
        if "workshop" in self.scopes:
            fixture = self.paths.repo_root / WORKSHOP_FIXTURE_RELATIVE
            if not fixture.is_dir():
                raise ResetSafetyError(f"Missing workshop fixture: {fixture}")

    def apply(self, *, allow_running_backend: bool = False) -> dict:
        self.validate(allow_running_backend=allow_running_backend)
        self.paths.backup_root.mkdir(parents=True, exist_ok=False)
        _backup_sqlite(
            self.paths.main_db,
            self.paths.backup_root / self.paths.main_db.name,
        )
        _backup_sqlite(
            self.paths.archive_db,
            self.paths.backup_root / self.paths.archive_db.name,
        )

        report: dict[str, object] = {
            "backup_root": str(self.paths.backup_root),
            "scopes": list(self.scopes),
            "moved_paths": [],
            "archived_task_count": 0,
        }
        if "initial" in self.scopes:
            self._reset_initial(report)
        if "incremental" in self.scopes:
            self._reset_incremental(report)
        if "workshop" in self.scopes:
            self._reset_workshop(report)
        if "neologism" in self.scopes:
            self._reset_neologism(report)
        report["archived_task_count"] = self._archive_demo_tasks()
        return report

    def _move_to_backup(self, path: Path, report: dict, *, label: str) -> None:
        if not path.exists():
            return
        allowed_roots = [
            self.paths.app_data_dir,
            *self.worktree_roots,
            self.paths.fixture_repo_root,
        ]
        if not any(_is_relative_to(path, root) for root in allowed_roots):
            raise ResetSafetyError(f"Refusing to move out-of-scope {label}: {path}")
        destination = self.paths.backup_root / "files" / label
        counter = 1
        while destination.exists():
            counter += 1
            destination = self.paths.backup_root / "files" / f"{label}-{counter}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(destination))
        report["moved_paths"].append(
            {"source": str(path), "backup": str(destination)}
        )

    def _project(self, project_id: str) -> sqlite3.Row:
        connection = sqlite3.connect(self.paths.main_db)
        connection.row_factory = sqlite3.Row
        try:
            row = connection.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise ResetSafetyError(f"Official demo project is missing: {project_id}")
        return row

    def _resolve_stored_path(self, raw_path: str) -> Path:
        normalized = str(raw_path or "").replace("\\", "/")
        replacements = {
            "{{APP_DATA_DIR}}": self.paths.app_data_dir.as_posix(),
            "{{PROJECT_ROOT}}": self.paths.repo_root.as_posix(),
            "{{BUNDLED_DEMO_ROOT}}": (
                self.paths.app_data_dir / "demos"
            ).as_posix(),
            "{{BUNDLED_TRANSLATION_ROOT}}": (
                self.paths.app_data_dir / "my_translation"
            ).as_posix(),
        }
        for placeholder, value in replacements.items():
            if normalized == placeholder or normalized.startswith(placeholder + "/"):
                normalized = value + normalized[len(placeholder):]
                break
        return Path(os.path.normpath(normalized))

    def _relativize_app_data_path(self, path: Path) -> str:
        relative = path.resolve().relative_to(self.paths.app_data_dir.resolve())
        return "{{APP_DATA_DIR}}/" + relative.as_posix()

    def _reset_initial(self, report: dict) -> None:
        project = self._project(EU5_PROJECT_ID)
        target = self._resolve_stored_path(project["target_path"])
        _require_within(
            target,
            self.paths.app_data_dir / "my_translation",
            label="EU5 demo translation target",
        )
        self._move_to_backup(target, report, label="initial-eu5-translation")
        target.mkdir(parents=True, exist_ok=True)
        self._clear_archive_translations(EU5_PROJECT_ID)
        with sqlite3.connect(self.paths.main_db) as connection:
            connection.execute(
                """
                DELETE FROM project_files
                WHERE project_id = ? AND file_type = 'translation'
                """,
                (EU5_PROJECT_ID,),
            )
            connection.commit()

    def _clear_archive_translations(self, project_id: str) -> None:
        with sqlite3.connect(self.paths.archive_db) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            mod_row = connection.execute(
                """
                SELECT mod_id FROM mod_identities
                WHERE remote_file_id = ?
                """,
                (project_id,),
            ).fetchone()
            if mod_row:
                connection.execute(
                    """
                    DELETE FROM translated_entries
                    WHERE source_entry_id IN (
                        SELECT source_entry_id FROM source_entries
                        WHERE version_id IN (
                            SELECT version_id FROM source_versions
                            WHERE mod_id = ?
                        )
                    )
                    """,
                    (mod_row[0],),
                )
            connection.commit()

    def _restore_repo_fixture(self, relative: Path, report: dict) -> None:
        source = self.paths.fixture_repo_root / relative
        target = self.paths.app_data_dir / "demos" / relative.name
        _require_within(
            target,
            self.paths.app_data_dir / "demos",
            label="demo source target",
        )
        self._move_to_backup(
            target,
            report,
            label=f"incremental-source-{relative.name}",
        )
        shutil.copytree(source, target)
        sidecar = target / ".remis_project.json"
        if sidecar.is_file():
            content = sidecar.read_text(encoding="utf-8")
            content = content.replace(
                "{{BUNDLED_DEMO_ROOT}}",
                (self.paths.app_data_dir / "demos").as_posix(),
            )
            content = content.replace(
                "{{BUNDLED_TRANSLATION_ROOT}}",
                (self.paths.app_data_dir / "my_translation").as_posix(),
            )
            sidecar.write_text(content, encoding="utf-8")

    def _reset_incremental(self, report: dict) -> None:
        self._restore_repo_fixture(VIC3_BASE_RELATIVE, report)
        self._restore_repo_fixture(VIC3_UPDATE_RELATIVE, report)
        self._restore_archive_project_from_seed(VIC3_PROJECT_ID)

        project = self._project(VIC3_PROJECT_ID)
        target = self._resolve_stored_path(project["target_path"])
        _require_within(
            target,
            self.paths.app_data_dir / "my_translation",
            label="Vic3 baseline translation target",
        )
        self._move_to_backup(
            target,
            report,
            label="incremental-vic3-baseline-translation",
        )
        target_file = (
            target
            / "localization"
            / "english"
            / "remis_demo_l_english.yml"
        )
        self._materialize_vic3_baseline(target_file)

        output_paths = self._incremental_output_paths()
        for index, output_path in enumerate(sorted(output_paths), start=1):
            self._move_to_backup(
                output_path,
                report,
                label=f"incremental-generated-output-{index}",
            )
        self._clean_project_sidecar(
            VIC3_PROJECT_ID,
            remove_incremental=True,
            ensure_dirs=[target],
        )
        with sqlite3.connect(self.paths.main_db) as connection:
            connection.execute(
                """
                DELETE FROM project_files
                WHERE project_id = ?
                  AND (
                    file_path LIKE '%-incremental-update-%'
                    OR file_path LIKE '%incremental_update%'
                  )
                """,
                (VIC3_PROJECT_ID,),
            )
            if _table_exists(connection, "project_history"):
                connection.execute(
                    """
                    DELETE FROM project_history
                    WHERE project_id = ?
                      AND action_type IN ('translate', 'path_registered')
                    """,
                    (VIC3_PROJECT_ID,),
                )
            connection.commit()

    def _restore_archive_project_from_seed(self, project_id: str) -> None:
        with sqlite3.connect(self.paths.archive_db) as destination:
            destination.execute("PRAGMA foreign_keys = ON")
            destination.row_factory = sqlite3.Row
            source = sqlite3.connect(self.paths.archive_seed_db)
            source.row_factory = sqlite3.Row
            try:
                seed_mod = source.execute(
                    """
                    SELECT m.* FROM mods m
                    JOIN mod_identities i ON i.mod_id = m.mod_id
                    WHERE i.remote_file_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                if seed_mod is None:
                    raise ResetSafetyError(
                        f"Archive seed lacks demo project {project_id}"
                    )
                current_mod = destination.execute(
                    """
                    SELECT m.mod_id FROM mods m
                    JOIN mod_identities i ON i.mod_id = m.mod_id
                    WHERE i.remote_file_id = ?
                    """,
                    (project_id,),
                ).fetchone()
                if current_mod is None:
                    cursor = destination.execute(
                        "INSERT INTO mods (name, last_updated) VALUES (?, ?)",
                        (seed_mod["name"], seed_mod["last_updated"]),
                    )
                    mod_id = int(cursor.lastrowid)
                    destination.execute(
                        """
                        INSERT INTO mod_identities (mod_id, remote_file_id)
                        VALUES (?, ?)
                        """,
                        (mod_id, project_id),
                    )
                else:
                    mod_id = int(current_mod["mod_id"])

                destination.execute(
                    """
                    DELETE FROM translated_entries
                    WHERE source_entry_id IN (
                        SELECT source_entry_id FROM source_entries
                        WHERE version_id IN (
                            SELECT version_id FROM source_versions
                            WHERE mod_id = ?
                        )
                    )
                    """,
                    (mod_id,),
                )
                destination.execute(
                    """
                    DELETE FROM source_entries
                    WHERE version_id IN (
                        SELECT version_id FROM source_versions
                        WHERE mod_id = ?
                    )
                    """,
                    (mod_id,),
                )
                destination.execute(
                    "DELETE FROM source_versions WHERE mod_id = ?",
                    (mod_id,),
                )

                versions = source.execute(
                    """
                    SELECT * FROM source_versions
                    WHERE mod_id = ?
                    ORDER BY version_id
                    """,
                    (seed_mod["mod_id"],),
                ).fetchall()
                for version in versions:
                    version_cursor = destination.execute(
                        """
                        INSERT INTO source_versions (
                            mod_id, snapshot_hash, created_at
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            mod_id,
                            version["snapshot_hash"],
                            version["created_at"],
                        ),
                    )
                    new_version_id = int(version_cursor.lastrowid)
                    entries = source.execute(
                        """
                        SELECT * FROM source_entries
                        WHERE version_id = ?
                        ORDER BY source_entry_id
                        """,
                        (version["version_id"],),
                    ).fetchall()
                    for entry in entries:
                        entry_cursor = destination.execute(
                            """
                            INSERT INTO source_entries (
                                version_id, entry_key, source_text, file_path
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                new_version_id,
                                entry["entry_key"],
                                entry["source_text"],
                                entry["file_path"],
                            ),
                        )
                        new_entry_id = int(entry_cursor.lastrowid)
                        translations = source.execute(
                            """
                            SELECT * FROM translated_entries
                            WHERE source_entry_id = ?
                            ORDER BY translated_entry_id
                            """,
                            (entry["source_entry_id"],),
                        ).fetchall()
                        destination.executemany(
                            """
                            INSERT INTO translated_entries (
                                source_entry_id, language_code,
                                translated_text, last_translated_at
                            )
                            VALUES (?, ?, ?, ?)
                            """,
                            [
                                (
                                    new_entry_id,
                                    translation["language_code"],
                                    translation["translated_text"],
                                    translation["last_translated_at"],
                                )
                                for translation in translations
                            ],
                        )
                destination.commit()
            finally:
                source.close()

    def _materialize_vic3_baseline(self, target_file: Path) -> None:
        with sqlite3.connect(self.paths.archive_db) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT s.entry_key, t.translated_text
                FROM mod_identities i
                JOIN source_versions v ON v.mod_id = i.mod_id
                JOIN source_entries s ON s.version_id = v.version_id
                JOIN translated_entries t
                  ON t.source_entry_id = s.source_entry_id
                WHERE i.remote_file_id = ?
                  AND t.language_code = 'en'
                  AND s.file_path LIKE '%remis_demo_l_simp_chinese.yml'
                  AND v.version_id = (
                      SELECT v2.version_id
                      FROM source_versions v2
                      JOIN source_entries s2 ON s2.version_id = v2.version_id
                      JOIN translated_entries t2
                        ON t2.source_entry_id = s2.source_entry_id
                      WHERE v2.mod_id = i.mod_id
                        AND t2.language_code = 'en'
                      GROUP BY v2.version_id
                      ORDER BY MAX(t2.last_translated_at) DESC,
                               v2.created_at DESC,
                               v2.version_id DESC
                      LIMIT 1
                  )
                ORDER BY s.source_entry_id
                """,
                (VIC3_PROJECT_ID,),
            ).fetchall()
        if not rows:
            raise ResetSafetyError("Vic3 archive baseline has no English entries")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        lines = ["l_english:"]
        for row in rows:
            value = str(row["translated_text"]).replace("\\", "\\\\")
            value = value.replace('"', '\\"').replace("\r", "").replace("\n", "\\n")
            lines.append(f' {row["entry_key"]} "{value}"')
        target_file.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

    def _incremental_output_paths(self) -> set[Path]:
        paths: set[Path] = set()
        with sqlite3.connect(self.paths.main_db) as connection:
            connection.row_factory = sqlite3.Row
            if _table_exists(connection, "project_history"):
                for row in connection.execute(
                    """
                    SELECT extra_metadata FROM project_history
                    WHERE project_id = ? AND action_type = 'translate'
                    """,
                    (VIC3_PROJECT_ID,),
                ):
                    output = _json_dict(row["extra_metadata"]).get("output_dir")
                    if output:
                        paths.add(self._resolve_stored_path(str(output)))
            if _table_exists(connection, "background_tasks"):
                for row in connection.execute(
                    """
                    SELECT result FROM background_tasks
                    WHERE project_id = ? AND kind = 'incremental_translation'
                    """,
                    (VIC3_PROJECT_ID,),
                ):
                    for output in _json_dict(row["result"]).get("output_paths", []):
                        candidate = Path(str(output))
                        if candidate.suffix.lower() == ".log":
                            candidate = candidate.parent
                        paths.add(candidate)

        known_names = {path.name for path in paths if "incremental-update" in path.name}
        for root in self.worktree_roots:
            translation_root = root / "my_translation"
            for name in known_names:
                candidate = translation_root / name
                if candidate.exists():
                    paths.add(candidate)
        return {
            path.resolve()
            for path in paths
            if path.exists() and "incremental-update" in path.name
        }

    def _project_sidecar(self, project_id: str) -> Path:
        project = self._project(project_id)
        source_path = self._resolve_stored_path(project["source_path"])
        _require_within(
            source_path,
            self.paths.app_data_dir / "demos",
            label="official demo source",
        )
        return source_path / ".remis_project.json"

    def _clean_project_sidecar(
        self,
        project_id: str,
        *,
        remove_incremental: bool = False,
        ensure_dirs: Sequence[Path] = (),
    ) -> None:
        sidecar = self._project_sidecar(project_id)
        data = (
            json.loads(sidecar.read_text(encoding="utf-8"))
            if sidecar.exists()
            else {}
        )
        config = data.setdefault("config", {})
        current = [
            str(self._resolve_stored_path(str(item)).resolve())
            for item in (config.get("translation_dirs") or [])
            if item
        ]
        if remove_incremental:
            current = [
                item
                for item in current
                if "incremental-update" not in str(item)
                and "incremental_update" not in str(item)
            ]
        for path in ensure_dirs:
            normalized = str(path.resolve())
            if normalized not in current:
                current.append(normalized)
        deduplicated: dict[str, str] = {}
        for item in current:
            deduplicated.setdefault(os.path.normcase(item), item)
        config["translation_dirs"] = list(deduplicated.values())
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        temporary = sidecar.with_suffix(sidecar.suffix + ".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, sidecar)

    def _reset_workshop(self, report: dict) -> None:
        fixture_source = self.paths.repo_root / WORKSHOP_FIXTURE_RELATIVE
        fixture_target = (
            self.paths.app_data_dir
            / "demo_smoke"
            / "agent_workshop_broken"
        )
        _require_within(
            fixture_target,
            self.paths.app_data_dir / "demo_smoke",
            label="workshop fixture",
        )
        self._move_to_backup(
            fixture_target,
            report,
            label="workshop-broken-fixture",
        )
        shutil.copytree(fixture_source, fixture_target)
        self._clean_project_sidecar(
            STELLARIS_PROJECT_ID,
            ensure_dirs=[fixture_target],
        )
        with sqlite3.connect(self.paths.main_db) as connection:
            connection.execute(
                """
                DELETE FROM project_files
                WHERE project_id = ?
                  AND file_path LIKE '%demo_smoke%agent_workshop_broken%'
                """,
                (STELLARIS_PROJECT_ID,),
            )
            for file_path in fixture_target.rglob("*.yml"):
                stored_path = self._relativize_app_data_path(file_path)
                file_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        str(file_path.resolve()).lower().replace("\\", "/"),
                    )
                )
                line_count = len(
                    file_path.read_text(
                        encoding="utf-8-sig",
                    ).splitlines()
                )
                connection.execute(
                    """
                    INSERT INTO project_files (
                        file_id, project_id, file_path, status,
                        original_key_count, line_count, file_type
                    )
                    VALUES (?, ?, ?, 'todo', 0, ?, 'translation')
                    ON CONFLICT(project_id, file_path) DO UPDATE SET
                        line_count = excluded.line_count,
                        file_type = excluded.file_type,
                        status = 'todo'
                    """,
                    (
                        file_id,
                        STELLARIS_PROJECT_ID,
                        stored_path,
                        line_count,
                    ),
                )
            connection.commit()

    def _reset_neologism(self, report: dict) -> None:
        cache_name = _candidate_cache_name(STELLARIS_PROJECT_ID)
        for index, root in enumerate(self.worktree_roots, start=1):
            candidate = root / "data" / "cache" / "neologism_candidates" / cache_name
            self._move_to_backup(
                candidate,
                report,
                label=f"neologism-candidates-{index}",
            )
        with sqlite3.connect(self.paths.main_db) as connection:
            connection.row_factory = sqlite3.Row
            bindings = connection.execute(
                """
                SELECT b.glossary_id, g.raw_metadata
                FROM project_glossary_bindings b
                JOIN glossaries g ON g.glossary_id = b.glossary_id
                WHERE b.project_id = ?
                """,
                (STELLARIS_PROJECT_ID,),
            ).fetchall()
            owned_ids = [
                int(row["glossary_id"])
                for row in bindings
                if (
                    _json_dict(row["raw_metadata"]).get("owner_project_id")
                    == STELLARIS_PROJECT_ID
                    or _json_dict(row["raw_metadata"]).get("project_id")
                    == STELLARIS_PROJECT_ID
                )
            ]
            for glossary_id in owned_ids:
                connection.execute(
                    "DELETE FROM entries WHERE glossary_id = ?",
                    (glossary_id,),
                )
                connection.execute(
                    """
                    DELETE FROM project_glossary_bindings
                    WHERE glossary_id = ?
                    """,
                    (glossary_id,),
                )
                connection.execute(
                    "DELETE FROM glossaries WHERE glossary_id = ?",
                    (glossary_id,),
                )
            connection.commit()
        report["deleted_stellaris_project_glossary_ids"] = owned_ids

    def _archive_demo_tasks(self) -> int:
        project_ids: list[str] = []
        if "initial" in self.scopes:
            project_ids.append(EU5_PROJECT_ID)
        if "incremental" in self.scopes:
            project_ids.append(VIC3_PROJECT_ID)
        if "workshop" in self.scopes or "neologism" in self.scopes:
            project_ids.append(STELLARIS_PROJECT_ID)
        if not project_ids:
            return 0
        archived_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        placeholders = ",".join("?" for _ in project_ids)
        status_placeholders = ",".join("?" for _ in TERMINAL_TASK_STATUSES)
        with sqlite3.connect(self.paths.main_db) as connection:
            if not _table_exists(connection, "background_tasks"):
                return 0
            cursor = connection.execute(
                f"""
                UPDATE background_tasks
                SET archived_at = ?, updated_at = ?
                WHERE project_id IN ({placeholders})
                  AND lower(status) IN ({status_placeholders})
                  AND archived_at IS NULL
                """,
                (
                    archived_at,
                    archived_at,
                    *project_ids,
                    *TERMINAL_TASK_STATUSES,
                ),
            )
            connection.commit()
            return max(0, int(cursor.rowcount))


def build_paths(
    *,
    repo_root: Path,
    fixture_repo_root: Path,
    app_data_dir: Path,
    backup_root: Path | None = None,
) -> ResetPaths:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return ResetPaths(
        repo_root=repo_root.resolve(),
        fixture_repo_root=fixture_repo_root.resolve(),
        app_data_dir=app_data_dir.resolve(),
        main_db=(app_data_dir / "remis.sqlite").resolve(),
        archive_db=(app_data_dir / "mods_cache.sqlite").resolve(),
        archive_seed_db=(repo_root / "assets" / "mods_cache_skeleton.sqlite").resolve(),
        backup_root=(
            backup_root
            or app_data_dir / "demo_smoke_backups" / timestamp
        ).resolve(),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reset official Remis demos for initial translation, incremental "
            "translation, Agent Workshop, and neologism smoke tests."
        )
    )
    parser.add_argument(
        "--scope",
        action="append",
        choices=(*SCOPES, "all"),
        help="Scope to reset. Repeat for multiple scopes; default: all.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Apply the reset. Without this flag, only print the preview.",
    )
    parser.add_argument(
        "--app-data-dir",
        type=Path,
        default=_default_app_data_dir(),
        help="Override the Remis development AppData directory.",
    )
    parser.add_argument(
        "--fixture-repo-root",
        type=Path,
        help="Override the primary repository containing the frozen fixtures.",
    )
    parser.add_argument(
        "--allow-running-backend",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable preview/result JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    scopes = args.scope or ["all"]
    if "all" in scopes:
        scopes = list(SCOPES)
    worktrees = discover_worktree_roots(REPO_ROOT)
    fixture_repo_root = (
        args.fixture_repo_root
        or select_fixture_repo_root(REPO_ROOT, worktrees)
    )
    paths = build_paths(
        repo_root=REPO_ROOT,
        fixture_repo_root=fixture_repo_root,
        app_data_dir=args.app_data_dir,
    )
    reset = DemoSmokeReset(paths, scopes, worktree_roots=worktrees)
    preview = {
        "mode": "apply" if args.yes else "preview",
        "scopes": list(reset.scopes),
        "app_data_dir": str(paths.app_data_dir),
        "fixture_repo_root": str(paths.fixture_repo_root),
        "actions": reset.preview(),
    }
    if not args.yes:
        if args.json:
            print(json.dumps(preview, ensure_ascii=False, indent=2))
        else:
            print("Remis demo smoke reset preview")
            print(f"AppData: {paths.app_data_dir}")
            print(f"Fixture repo: {paths.fixture_repo_root}")
            for action in preview["actions"]:
                print(f"  - {action}")
            print("\nNo changes made. Re-run with --yes to apply.")
        return 0
    try:
        result = reset.apply(
            allow_running_backend=args.allow_running_backend,
        )
    except ResetSafetyError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Remis demo smoke fixtures are ready.")
        print(f"Backup: {result['backup_root']}")
        print(f"Archived demo tasks: {result['archived_task_count']}")
        print(f"Moved prior paths: {len(result['moved_paths'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
