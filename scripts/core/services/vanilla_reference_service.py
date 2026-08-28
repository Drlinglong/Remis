"""Deterministic exact-match reuse from a user-selected vanilla localization tree.

Key-only and fuzzy matches are never accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import os
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager
from typing import Callable, Iterable, Iterator, Optional

from scripts.app_settings import LANGUAGES, VANILLA_REFERENCE_DB_PATH
from scripts.core.paradox_localization_parser import parse_text
from scripts.core.services.paradox_installation_discovery import official_localization_roots
from scripts.core.services.reference_db_lock import (
    REFERENCE_DB_WRITE_LOCK,
    serialized_reference_write,
)
from scripts.core.services.trusted_reference_paths import trusted_reference_roots
from scripts.core.services.vanilla_reference_version import detect_reference_game_version


logger = logging.getLogger(__name__)
_VERSION_SUFFIX_RE = re.compile(r":\d+$")


def _report_progress(callback: Optional[Callable[[dict], None]], **updates: object) -> None:
    if callback is None:
        return
    try:
        callback(updates)
    except Exception:
        logger.debug("Reference progress callback failed", exc_info=True)

def normalize_reference_key(key: str) -> str:
    """Return the semantic Paradox key without its translation revision."""

    return _VERSION_SUFFIX_RE.sub("", (key or "").strip())


def normalize_reference_source_file(source_file: str) -> str:
    return str(source_file or "").replace("\\", "/").strip("/").casefold()

def _build_excluded_identities(
    excluded_entries: Optional[Iterable[dict]],
    target_lang_code: str,
) -> set[tuple[str, str, str]]:
    return {
        (
            normalize_reference_source_file(entry.get("file_path", "")),
            normalize_reference_key(entry.get("key", "")),
            str(entry.get("source_text", "")),
        )
        for entry in (excluded_entries or ())
        if isinstance(entry, dict) and entry.get("target_lang_code") == target_lang_code
    }


@dataclass(frozen=True)
class ReferenceLookupResult:
    status: str
    translation: Optional[str] = None

    @property
    def hit(self) -> bool:
        return self.status == "hit" and self.translation is not None


@dataclass(frozen=True)
class ReferenceIndexInfo:
    reference_set_id: int
    game_id: str
    game_version: str
    root_path: str
    stat_fingerprint: str
    content_fingerprint: str
    created_at: str
    stale: bool = False


class VanillaReferenceResolver:
    """In-memory lookup view for one source/target language pair."""

    def __init__(
        self,
        rows: dict[str, tuple[tuple[Optional[str], Optional[str], bool, bool], ...]],
        info: ReferenceIndexInfo,
        target_lang_code: str,
        excluded_entries: Optional[Iterable[dict]] = None,
    ) -> None:
        self._rows = rows
        self.info = info
        self._excluded_identities = _build_excluded_identities(
            excluded_entries,
            target_lang_code,
        )
        self._metrics = {
            "reference_matched": 0,
            "api_skipped": 0,
            "conflicts": 0,
            "missing_targets": 0,
            "source_mismatches": 0,
            "reference_misses": 0,
            "reference_deselected": 0,
            "stale_reference_hits": 0,
        }

    def lookup(
        self,
        key: str,
        source_text: str,
        source_file: str = "",
    ) -> ReferenceLookupResult:
        rows = self._rows.get(normalize_reference_key(key))
        if rows is None:
            self._metrics["reference_misses"] += 1
            return ReferenceLookupResult("key_missing")

        candidates = [row for row in rows if row[0] == source_text]
        if not candidates:
            if any(row[2] for row in rows):
                self._metrics["conflicts"] += 1
                return ReferenceLookupResult("conflict")
            self._metrics["source_mismatches"] += 1
            return ReferenceLookupResult("source_mismatch")
        if any(row[2] or row[3] for row in candidates):
            self._metrics["conflicts"] += 1
            return ReferenceLookupResult("conflict")
        target_values = {row[1] for row in candidates if row[1] is not None}
        if not target_values:
            self._metrics["missing_targets"] += 1
            return ReferenceLookupResult("missing_target")
        if len(target_values) != 1 or any(row[1] is None for row in candidates):
            self._metrics["conflicts"] += 1
            return ReferenceLookupResult("conflict")
        target_text = next(iter(target_values))
        identity = (
            normalize_reference_source_file(source_file),
            normalize_reference_key(key),
            source_text,
        )
        if identity in self._excluded_identities:
            self._metrics["reference_deselected"] += 1
            return ReferenceLookupResult("deselected")

        self._metrics["reference_matched"] += 1
        self._metrics["api_skipped"] += 1
        if self.info.stale:
            self._metrics["stale_reference_hits"] += 1
        return ReferenceLookupResult("hit", target_text)

    def metrics(self) -> dict[str, int | bool | str]:
        return {
            **self._metrics,
            "reference_enabled": True,
            "reference_stale": self.info.stale,
            "reference_game_version": self.info.game_version,
            "reference_content_fingerprint": self.info.content_fingerprint,
        }


class VanillaReferenceService:
    """Build and open versioned multilingual SQLite reference sets."""

    def __init__(
        self,
        db_path: str | Path = VANILLA_REFERENCE_DB_PATH,
        *,
        trusted_roots: Optional[Iterable[str | Path]] = None,
    ) -> None:
        self.db_path = Path(db_path)
        self._trusted_roots = trusted_reference_roots(self.db_path, trusted_roots)

    def open_resolver(
        self,
        *,
        game_id: str,
        localization_root: str | Path,
        source_lang_code: str,
        target_lang_code: str,
        supported_language_keys: Optional[Iterable[str]] = None,
        excluded_entries: Optional[Iterable[dict]] = None,
        encoding: str = "utf-8-sig",
    ) -> VanillaReferenceResolver:
        info = self.build_index(
            game_id=game_id,
            localization_root=localization_root,
            supported_language_keys=supported_language_keys,
            encoding=encoding,
        )
        rows = self._load_language_pair(
            info.reference_set_id,
            source_lang_code,
            target_lang_code,
        )
        return VanillaReferenceResolver(
            rows,
            info,
            target_lang_code,
            excluded_entries,
        )

    @serialized_reference_write
    def build_index(
        self,
        *,
        game_id: str,
        localization_root: str | Path,
        localization_globs: Optional[Iterable[str]] = None,
        supported_language_keys: Optional[Iterable[str]] = None,
        encoding: str = "utf-8-sig",
        progress_callback: Optional[Callable[[dict], None]] = None,
        allow_stale_fallback: bool = True,
        force_rebuild: bool = False,
    ) -> ReferenceIndexInfo:
        """Build and activate a multilingual index for an explicit source tree."""

        root = self._validate_root(localization_root, localization_globs)
        _report_progress(progress_callback, stage="scanning", files_current=0)
        files_by_language = self._collect_language_files(
            root,
            supported_language_keys,
            localization_globs,
        )
        _report_progress(
            progress_callback,
            stage="scanning",
            files_current=0,
            files_total=sum(len(files) for files in files_by_language.values()),
        )
        game_version = self._detect_game_version(root)
        stat_fingerprint = self._stat_fingerprint(root, files_by_language, game_version)

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                """
                SELECT * FROM reference_sets_v2
                WHERE game_id = ? AND game_version = ?
                  AND root_path = ? AND stat_fingerprint = ?
                ORDER BY reference_set_id DESC LIMIT 1
                """,
                (game_id, game_version, str(root), stat_fingerprint),
            ).fetchone()

        stale = False
        if row is None or force_rebuild:
            try:
                row = self._build_reference_set(
                    game_id=game_id,
                    game_version=game_version,
                    root=root,
                    files_by_language=files_by_language,
                    stat_fingerprint=stat_fingerprint,
                    encoding=encoding,
                    progress_callback=progress_callback,
                    replace_existing=force_rebuild,
                )
            except Exception:
                logger.exception("Failed to rebuild vanilla reference index for %s", root)
                if not allow_stale_fallback:
                    raise
                with self._connect() as connection:
                    self._ensure_schema(connection)
                    row = connection.execute(
                        """
                        SELECT * FROM reference_sets_v2
                        WHERE game_id = ? AND root_path = ?
                        ORDER BY reference_set_id DESC LIMIT 1
                        """,
                        (game_id, str(root)),
                    ).fetchone()
                if row is None:
                    raise
                stale = True

        info = self._row_to_info(row, stale=stale)
        _report_progress(
            progress_callback,
            stage="activating",
            files_current=sum(len(files) for files in files_by_language.values()),
            files_total=sum(len(files) for files in files_by_language.values()),
            entries_current=self.count_entries(info.reference_set_id),
        )
        self.activate_reference_set(info.reference_set_id, game_id)
        _report_progress(
            progress_callback,
            stage="completed",
            files_current=sum(len(files) for files in files_by_language.values()),
            files_total=sum(len(files) for files in files_by_language.values()),
            entries_current=self.count_entries(info.reference_set_id),
        )
        return info

    def open_active_resolver(
        self,
        *,
        game_id: str,
        source_lang_code: str,
        target_lang_code: str,
        excluded_entries: Optional[Iterable[dict]] = None,
    ) -> Optional[VanillaReferenceResolver]:
        """Open the explicitly built active index without rescanning source files."""

        info = self.get_active_index(game_id)
        if info is None:
            return None
        rows = self._load_language_pair(
            info.reference_set_id,
            source_lang_code,
            target_lang_code,
        )
        return VanillaReferenceResolver(rows, info, target_lang_code, excluded_entries)

    def activate_reference_set(self, reference_set_id: int, game_id: str) -> None:
        with REFERENCE_DB_WRITE_LOCK:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as connection:
                self._ensure_schema(connection)
                connection.execute(
                    """
                    INSERT INTO active_reference_sets (game_id, reference_set_id, activated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(game_id) DO UPDATE SET
                        reference_set_id = excluded.reference_set_id,
                        activated_at = excluded.activated_at
                    """,
                    (game_id, reference_set_id, datetime.now(timezone.utc).isoformat()),
                )

    def get_active_index(self, game_id: str) -> Optional[ReferenceIndexInfo]:
        if not self.db_path.is_file():
            return None
        with self._connect() as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                """
                SELECT reference_sets_v2.*
                FROM active_reference_sets
                JOIN reference_sets_v2 USING(reference_set_id)
                WHERE active_reference_sets.game_id = ?
                """,
                (game_id,),
            ).fetchone()
        if row is None:
            return None
        root = Path(row["root_path"])
        current_version = self._detect_game_version(root)
        stale = not root.is_dir() or current_version not in {"unknown", row["game_version"]}
        return self._row_to_info(row, stale=stale)

    def list_active_indexes(self) -> list[ReferenceIndexInfo]:
        if not self.db_path.is_file():
            return []
        with self._connect() as connection:
            self._ensure_schema(connection)
            game_ids = [
                row["game_id"]
                for row in connection.execute(
                    "SELECT game_id FROM active_reference_sets ORDER BY game_id"
                )
            ]
        return [info for game_id in game_ids if (info := self.get_active_index(game_id))]

    def count_entries(self, reference_set_id: int) -> int:
        with self._connect() as connection:
            self._ensure_schema(connection)
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM reference_entries_v2 WHERE reference_set_id = ?",
                (reference_set_id,),
            ).fetchone()
        return int(row["count"])

    def delete_game_reference(self, game_id: str) -> dict[str, int | bool]:
        """Atomically remove a game's binding, sets, and all indexed entries."""

        with REFERENCE_DB_WRITE_LOCK:
            if not self.db_path.is_file():
                return {
                    "reference_sets_deleted": 0,
                    "entries_deleted": 0,
                    "database_compacted": True,
                }
            with self._connect() as connection:
                self._ensure_schema(connection)
                set_ids = [
                    row["reference_set_id"]
                    for row in connection.execute(
                        "SELECT reference_set_id FROM reference_sets_v2 WHERE game_id = ?",
                        (game_id,),
                    )
                ]
                entries_deleted = 0
                if set_ids:
                    placeholders = ", ".join("?" for _ in set_ids)
                    entries_deleted = connection.execute(
                        f"DELETE FROM reference_entries_v2 WHERE reference_set_id IN ({placeholders})",
                        set_ids,
                    ).rowcount
                connection.execute("DELETE FROM active_reference_sets WHERE game_id = ?", (game_id,))
                sets_deleted = connection.execute(
                    "DELETE FROM reference_sets_v2 WHERE game_id = ?", (game_id,)
                ).rowcount
            database_compacted = self._compact_database()
            return {
                "reference_sets_deleted": int(sets_deleted),
                "entries_deleted": int(entries_deleted),
                "database_compacted": database_compacted,
            }

    def _compact_database(self) -> bool:
        """Return freed reference-library pages to the filesystem after deletion."""

        with REFERENCE_DB_WRITE_LOCK:
            try:
                with sqlite3.connect(self.db_path, timeout=30, isolation_level=None) as connection:
                    connection.execute("VACUUM")
            except sqlite3.Error:
                logger.warning(
                    "Reference entries were deleted, but SQLite space reclamation failed for %s",
                    self.db_path,
                    exc_info=True,
                )
                return False
            return True

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @serialized_reference_write
    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        """Serialize schema DDL with reference database writes and VACUUM."""

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reference_sets_v2 (
                reference_set_id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                game_version TEXT NOT NULL DEFAULT 'unknown',
                root_path TEXT NOT NULL,
                stat_fingerprint TEXT NOT NULL,
                content_fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(game_id, root_path, stat_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS reference_entries_v2 (
                reference_set_id INTEGER NOT NULL,
                language_code TEXT NOT NULL,
                entry_key TEXT NOT NULL,
                entry_text TEXT,
                is_conflict INTEGER NOT NULL DEFAULT 0,
                source_file TEXT,
                file_identity TEXT NOT NULL,
                PRIMARY KEY(reference_set_id, language_code, file_identity, entry_key),
                FOREIGN KEY(reference_set_id) REFERENCES reference_sets_v2(reference_set_id)
            );
            CREATE INDEX IF NOT EXISTS idx_reference_lookup_v2
                ON reference_entries_v2(reference_set_id, language_code, entry_key);
            CREATE TABLE IF NOT EXISTS active_reference_sets (
                game_id TEXT PRIMARY KEY,
                reference_set_id INTEGER NOT NULL,
                activated_at TEXT NOT NULL,
                FOREIGN KEY(reference_set_id) REFERENCES reference_sets_v2(reference_set_id)
            );
            """
        )
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reference_sets_v2)")
        }
        if "game_version" not in columns:
            connection.execute(
                "ALTER TABLE reference_sets_v2 ADD COLUMN game_version TEXT NOT NULL DEFAULT 'unknown'"
            )

    def _validate_root(
        self,
        localization_root: str | Path,
        localization_globs: Optional[Iterable[str]] = None,
    ) -> Path:
        candidate = os.path.realpath(os.path.expanduser(os.fspath(localization_root)))
        candidate_key = os.path.normcase(candidate)
        if not any(
            candidate_key == trusted or candidate_key.startswith(trusted.rstrip(os.sep) + os.sep)
            for trusted in self._trusted_roots
        ):
            raise ValueError("Reference path must belong to a trusted Steam library")
        root = Path(candidate)
        if not root.is_dir():
            raise ValueError(f"Reference localization path is not a directory: {root}")
        if localization_globs:
            if not official_localization_roots(
                root,
                {"official_localization_globs": list(localization_globs)},
            ):
                raise ValueError(f"No configured official localization directories found under {root}")
            return root
        if root.name.lower() not in {"localization", "localisation"}:
            raise ValueError("Reference path must be the game's localization/localisation directory")
        if root.parent.name.lower() != "game":
            raise ValueError("Reference path must be located directly under the game's game directory")
        return root

    def _collect_language_files(
        self,
        root: Path,
        supported_language_keys: Optional[Iterable[str]],
        localization_globs: Optional[Iterable[str]] = None,
    ) -> dict[str, tuple[Path, ...]]:
        allowed = set(str(key) for key in (supported_language_keys or ()))
        localization_roots = [root]
        if localization_globs:
            localization_roots = official_localization_roots(
                root,
                {"official_localization_globs": list(localization_globs)},
            )
        all_localization_files = tuple(
            path
            for localization_dir in localization_roots
            for path in localization_dir.rglob("*.yml")
            if path.is_file()
        )
        files_by_language: dict[str, tuple[Path, ...]] = {}
        for language_id, language in LANGUAGES.items():
            if allowed and language_id not in allowed:
                continue
            language_folder = language["key"][2:]
            flat_suffix = re.compile(
                rf"_l_{re.escape(language_folder)}\.yml$",
                flags=re.IGNORECASE,
            )
            files = tuple(sorted({
                path
                for localization_dir in localization_roots
                for path in (localization_dir / language_folder).rglob("*.yml")
                if path.is_file()
            } | {
                path for path in all_localization_files if flat_suffix.search(path.name)
            }))
            if files:
                files_by_language[language["code"]] = files
        if not files_by_language:
            raise ValueError(f"No supported vanilla localization files found under {root}")
        return files_by_language

    def _stat_fingerprint(
        self,
        root: Path,
        files_by_language: dict[str, tuple[Path, ...]],
        game_version: str,
    ) -> str:
        digest = hashlib.sha256()
        digest.update(f"game_version\0{game_version}\n".encode("utf-8"))
        for language_code in sorted(files_by_language):
            for path in files_by_language[language_code]:
                stat = path.stat()
                record = (
                    f"{language_code}\0{path.relative_to(root).as_posix()}\0"
                    f"{stat.st_size}\0{stat.st_mtime_ns}\n"
                )
                digest.update(record.encode("utf-8"))
        return digest.hexdigest()

    def _detect_game_version(self, root: Path) -> str:
        return detect_reference_game_version(root)

    def _logical_file_identity(self, relative_path: str, language_code: str) -> str:
        language = next(
            (item for item in LANGUAGES.values() if item.get("code") == language_code),
            {},
        )
        language_folder = str(language.get("key", ""))[2:]
        parts = relative_path.replace("\\", "/").split("/")
        parts = [part for part in parts if part.casefold() != language_folder.casefold()]
        if parts:
            parts[-1] = re.sub(
                rf"_l_{re.escape(language_folder)}(?=\.ya?ml$)",
                "",
                parts[-1],
                flags=re.IGNORECASE,
            )
        return "/".join(parts).casefold()

    def _build_reference_set(
        self,
        *,
        game_id: str,
        game_version: str,
        root: Path,
        files_by_language: dict[str, tuple[Path, ...]],
        stat_fingerprint: str,
        encoding: str,
        progress_callback: Optional[Callable[[dict], None]] = None,
        replace_existing: bool = False,
    ) -> sqlite3.Row:
        content_digest = hashlib.sha256()
        entries: dict[tuple[str, str, str], tuple[Optional[str], bool, str]] = {}

        files_total = sum(len(files) for files in files_by_language.values())
        files_current = 0
        entries_current = 0
        for language_code in sorted(files_by_language):
            for path in files_by_language[language_code]:
                raw = path.read_bytes()
                relative_path = path.relative_to(root).as_posix()
                file_identity = self._logical_file_identity(relative_path, language_code)
                content_digest.update(language_code.encode("utf-8"))
                content_digest.update(b"\0")
                content_digest.update(relative_path.encode("utf-8"))
                content_digest.update(b"\0")
                content_digest.update(raw)
                report = parse_text(raw.decode(encoding))
                if report.diagnostics:
                    logger.warning(
                        "Vanilla reference parser reported %s diagnostic(s) for %s",
                        len(report.diagnostics),
                        path,
                    )
                for entry in report.entries:
                    entries_current += 1
                    identity = (language_code, file_identity, entry.base_key)
                    previous = entries.get(identity)
                    if previous is None:
                        entries[identity] = (entry.value, False, relative_path)
                    elif previous[0] != entry.value:
                        entries[identity] = (None, True, relative_path)
                files_current += 1
                _report_progress(
                    progress_callback,
                    stage="indexing",
                    current_file=str(path),
                    files_current=files_current,
                    files_total=files_total,
                    entries_current=entries_current,
                )

        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            self._ensure_schema(connection)
            if replace_existing:
                self._remove_matching_reference_set(
                    connection,
                    game_id=game_id,
                    game_version=game_version,
                    root_path=str(root),
                    stat_fingerprint=stat_fingerprint,
                )
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO reference_sets_v2 (
                    game_id, game_version, root_path, stat_fingerprint,
                    content_fingerprint, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    game_id,
                    game_version,
                    str(root),
                    stat_fingerprint,
                    content_digest.hexdigest(),
                    created_at,
                ),
            )
            reference_set_id = cursor.lastrowid
            if not reference_set_id:
                row = connection.execute(
                    """
                    SELECT * FROM reference_sets_v2
                    WHERE game_id = ? AND game_version = ?
                      AND root_path = ? AND stat_fingerprint = ?
                    """,
                    (game_id, game_version, str(root), stat_fingerprint),
                ).fetchone()
                return row

            connection.executemany(
                """
                INSERT INTO reference_entries_v2 (
                    reference_set_id, language_code, entry_key, entry_text,
                    is_conflict, source_file, file_identity
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    (reference_set_id, language, key, text, int(conflict), source_file, file_identity)
                    for (language, file_identity, key), (text, conflict, source_file) in entries.items()
                ),
            )
            row = connection.execute(
                "SELECT * FROM reference_sets_v2 WHERE reference_set_id = ?",
                (reference_set_id,),
            ).fetchone()
        return row

    @staticmethod
    def _remove_matching_reference_set(
        connection: sqlite3.Connection,
        *,
        game_id: str,
        game_version: str,
        root_path: str,
        stat_fingerprint: str,
    ) -> None:
        existing = connection.execute(
            """
            SELECT reference_set_id FROM reference_sets_v2
            WHERE game_id = ? AND game_version = ?
              AND root_path = ? AND stat_fingerprint = ?
            """,
            (game_id, game_version, root_path, stat_fingerprint),
        ).fetchone()
        if existing is None:
            return
        existing_id = existing["reference_set_id"]
        connection.execute(
            "DELETE FROM active_reference_sets WHERE reference_set_id = ?",
            (existing_id,),
        )
        connection.execute(
            "DELETE FROM reference_entries_v2 WHERE reference_set_id = ?",
            (existing_id,),
        )
        connection.execute(
            "DELETE FROM reference_sets_v2 WHERE reference_set_id = ?",
            (existing_id,),
        )

    def _load_language_pair(
        self,
        reference_set_id: int,
        source_lang_code: str,
        target_lang_code: str,
    ) -> dict[str, tuple[tuple[Optional[str], Optional[str], bool, bool], ...]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT source.entry_key,
                       source.entry_text AS source_text,
                       source.is_conflict AS source_conflict,
                       target.entry_text AS target_text,
                       COALESCE(target.is_conflict, 0) AS target_conflict
                FROM reference_entries_v2 AS source
                LEFT JOIN reference_entries_v2 AS target
                  ON target.reference_set_id = source.reference_set_id
                 AND target.entry_key = source.entry_key
                 AND target.file_identity = source.file_identity
                 AND target.language_code = ?
                WHERE source.reference_set_id = ?
                  AND source.language_code = ?
                """,
                (target_lang_code, reference_set_id, source_lang_code),
            ).fetchall()
        result: dict[str, list[tuple[Optional[str], Optional[str], bool, bool]]] = {}
        for row in rows:
            result.setdefault(row["entry_key"], []).append((
                row["source_text"],
                row["target_text"],
                bool(row["source_conflict"]),
                bool(row["target_conflict"]),
            ))
        return {
            key: tuple(candidates)
            for key, candidates in result.items()
        }

    def _row_to_info(self, row: sqlite3.Row, *, stale: bool) -> ReferenceIndexInfo:
        return ReferenceIndexInfo(
            reference_set_id=int(row["reference_set_id"]),
            game_id=row["game_id"],
            game_version=row["game_version"],
            root_path=row["root_path"],
            stat_fingerprint=row["stat_fingerprint"],
            content_fingerprint=row["content_fingerprint"],
            created_at=row["created_at"],
            stale=stale,
        )
