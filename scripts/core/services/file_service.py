import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.utils.i18n_utils import iso_to_paradox

logger = logging.getLogger(__name__)

LOCALIZATION_DIR_NAMES = {"localization", "localisation"}
KNOWN_PARADOX_LANGUAGE_DIRS = {
    "braz_por",
    "chinese",
    "english",
    "french",
    "german",
    "japanese",
    "korean",
    "polish",
    "russian",
    "simp_chinese",
    "spanish",
    "trad_chinese",
    "turkish",
}
FILE_WORKFLOW_STATUSES = {"todo", "in_progress", "proofreading", "paused", "done"}


class FileService:
    """Read-only discovery of project localization files on disk."""

    @staticmethod
    def _source_language_in_path(path: str) -> str | None:
        parts = [part.lower() for part in Path(path).parts]
        for idx, part in enumerate(parts):
            if part in LOCALIZATION_DIR_NAMES:
                for nested in parts[idx + 1:]:
                    if nested in KNOWN_PARADOX_LANGUAGE_DIRS:
                        return nested
        return None

    @classmethod
    def _prune_non_source_language_dirs(cls, root: str, dirs: List[str], search_lang: str) -> bool:
        if not search_lang:
            return True

        normalized_search_lang = search_lang.lower()
        current_lang = cls._source_language_in_path(root)
        if current_lang and current_lang != normalized_search_lang:
            dirs[:] = []
            return False

        if Path(root).name.lower() in LOCALIZATION_DIR_NAMES:
            dirs[:] = [
                directory
                for directory in dirs
                if directory.lower() not in KNOWN_PARADOX_LANGUAGE_DIRS
                or directory.lower() == normalized_search_lang
            ]
        return True

    def scan_dir(
        self,
        root_path: str,
        file_type: str,
        search_lang: str,
        project_id: str,
        allowed_extensions: Optional[List[str]] = None,
        issues: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, Any]]:
        """Scan one directory without creating, repairing, or persisting anything."""
        if not os.path.isdir(root_path):
            logger.warning("FileService: Directory unavailable: %s", root_path)
            return []

        extensions = allowed_extensions or [".yml", ".yaml", ".txt", ".csv", ".json"]
        files_found: List[Dict[str, Any]] = []

        def record_walk_error(exc: OSError) -> None:
            logger.warning("FileService: Could not scan %s: %s", exc.filename or root_path, exc)
            if issues is not None:
                issues.append(
                    {
                        "code": "directory_scan_failed",
                        "file_type": file_type,
                        "path": str(exc.filename or root_path),
                    }
                )

        for root, dirs, files in os.walk(root_path, onerror=record_walk_error):
            dirs[:] = [directory for directory in dirs if not directory.startswith(".")]
            if file_type == "source" and not self._prune_non_source_language_dirs(root, dirs, search_lang):
                continue

            for filename in files:
                if not any(filename.lower().endswith(ext) for ext in extensions):
                    continue

                full_path = os.path.join(root, filename)
                try:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
                        line_count = sum(1 for _ in handle)
                except OSError as exc:
                    logger.warning("FileService: Could not read %s: %s", full_path, exc)
                    line_count = 0
                    if issues is not None:
                        issues.append(
                            {
                                "code": "file_read_failed",
                                "file_type": file_type,
                                "path": full_path,
                            }
                        )

                files_found.append(
                    {
                        "file_id": str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                full_path.lower().replace("\\", "/"),
                            )
                        ),
                        "project_id": project_id,
                        "file_path": full_path,
                        "status": "todo",
                        "original_key_count": 0,
                        "line_count": line_count,
                        "file_type": file_type,
                    }
                )

        logger.info("FileService: Discovered %s file(s) under %s", len(files_found), root_path)
        return files_found

    def discover_files(
        self,
        *,
        project_id: str,
        source_path: str,
        translation_dirs: List[str],
        source_language: str,
        game_id: str,
        status_by_file_id: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Build a transient disk manifest.

        This method deliberately has no repository, archive, or sidecar-writing
        dependency. Translation upload is the separate persistence boundary.
        """
        normalized_game_id = (game_id or "victoria3").lower()
        allowed_extensions = (
            [".yml", ".yaml", ".csv", ".txt"]
            if normalized_game_id == "eu4"
            else [".yml", ".yaml"]
        )
        disk_source_language = iso_to_paradox(source_language)
        warnings: List[Dict[str, str]] = []
        scanned_paths: List[str] = []
        files: List[Dict[str, Any]] = []

        unique_translation_dirs: List[str] = []
        seen_translation_dirs = set()
        for path in translation_dirs:
            canonical_path = os.path.normcase(os.path.abspath(path))
            if canonical_path in seen_translation_dirs:
                continue
            seen_translation_dirs.add(canonical_path)
            unique_translation_dirs.append(path)

        roots = [
            (source_path, "source"),
            *[(path, "translation") for path in unique_translation_dirs],
        ]
        for root_path, file_type in roots:
            if not os.path.isdir(root_path):
                warnings.append(
                    {
                        "code": "directory_unavailable",
                        "file_type": file_type,
                        "path": root_path,
                    }
                )
                continue
            scanned_paths.append(root_path)
            files.extend(
                self.scan_dir(
                    root_path,
                    file_type,
                    disk_source_language,
                    project_id,
                    allowed_extensions,
                    warnings,
                )
            )

        known_statuses = status_by_file_id or {}
        for file_record in files:
            previous_status = known_statuses.get(file_record["file_id"])
            if previous_status in FILE_WORKFLOW_STATUSES:
                file_record["status"] = previous_status
            elif previous_status:
                warnings.append(
                    {
                        "code": "invalid_file_status",
                        "file_type": file_record["file_type"],
                        "path": file_record["file_path"],
                    }
                )

        return {
            "project_id": project_id,
            "files": files,
            "file_count": len(files),
            "scanned_paths": scanned_paths,
            "warnings": warnings,
        }
