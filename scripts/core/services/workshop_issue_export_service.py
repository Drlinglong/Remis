import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.core.archive_manager import archive_manager
from scripts.core.loc_parser import parse_loc_file, parse_loc_file_with_lines
from scripts.utils.i18n_utils import iso_to_paradox
from scripts.utils.post_process_validator import PostProcessValidator
from scripts.utils.validation_logger import ValidationLogger

logger = logging.getLogger(__name__)


class WorkshopIssueExportService:
    """
    Builds a structured validation sidecar from translated output files.
    The resulting JSON is intended for Agent Workshop consumption.
    """

    OUTPUT_FILENAME = "workshop_issues.json"
    AGGREGATED_SIDE_CAR = ".remis_errors.json"

    def __init__(self):
        self.validator = PostProcessValidator()

    def export_for_output(
        self,
        output_root: str | Path,
        source_root: str | Path,
        source_lang_info: Dict[str, Any],
        target_lang_info: Dict[str, Any],
        game_profile: Dict[str, Any],
        workflow: str,
        project_name: str = "",
        project_id: str = "",
    ) -> Dict[str, Any]:
        output_root = Path(output_root)
        source_root = Path(source_root)
        output_root.mkdir(parents=True, exist_ok=True)

        generated_at = datetime.now().isoformat(timespec="seconds")
        issues: List[Dict[str, Any]] = []
        target_paradox = iso_to_paradox(target_lang_info.get("code", ""))
        source_paradox = iso_to_paradox(source_lang_info.get("code", ""))
        game_id = game_profile.get("id", "")

        if not output_root.exists():
            return self._write_exports(output_root, issues, generated_at)

        for translated_file in output_root.rglob("*.yml"):
            if not self._matches_target_language(translated_file, target_paradox):
                continue

            rel_output_path = self._normalize_relpath(translated_file.relative_to(output_root))
            source_file = self._resolve_source_file(
                translated_file=translated_file,
                output_root=output_root,
                source_root=source_root,
                source_paradox=source_paradox,
                target_paradox=target_paradox,
            )

            source_entries = self._load_source_entries(source_file)

            try:
                target_entries = parse_loc_file_with_lines(translated_file)
            except Exception as exc:
                logger.error(f"Failed to parse translated output file {translated_file}: {exc}")
                continue

            for key, value, line_number in target_entries:
                source_lookup = self._resolve_source_context(
                    source_entries=source_entries,
                    key=key,
                    source_file=source_file,
                    source_root=source_root,
                    translated_file=translated_file,
                    project_name=project_name,
                    project_id=project_id,
                )
                source_value = source_lookup["source_str"]
                try:
                    results = self.validator.validate_entry(
                        game_id=game_id,
                        key=key,
                        value=value,
                        line_number=line_number,
                        source_lang=source_lang_info,
                        source_value=source_value,
                        target_lang=target_lang_info.get("code"),
                    )
                except Exception as exc:
                    logger.error(f"Failed to validate {translated_file} [{key}]: {exc}")
                    continue

                for result in results:
                    if result.level.value not in {"error", "warning"}:
                        continue

                    issues.append({
                        "file_name": rel_output_path,
                        "file_path": str(translated_file),
                        "source_file": self._normalize_relpath(source_file.relative_to(source_root)) if source_file and source_file.exists() else "",
                        "key": key,
                        "line_number": result.line_number,
                        "source_str": source_value,
                        "source_context_status": source_lookup["status"],
                        "source_context_origin": source_lookup["origin"],
                        "source_context_warning": source_lookup.get("warning", ""),
                        "target_str": value,
                        "error_type": result.message,
                        "error_code": result.code or result.message,
                        "details": result.details or "",
                        "severity": result.level.value,
                        "status": "detected",
                        "workflow": workflow,
                        "game_id": game_id,
                        "project_name": project_name,
                        "target_lang": target_lang_info.get("code", ""),
                        "text_sample": result.text_sample or value[:100],
                        "generated_at": generated_at,
                    })

        export_result = self._write_exports(output_root, issues, generated_at)
        export_result["issue_count"] = len(issues)
        export_result["issues"] = issues
        return export_result

    def merge_exports(
        self,
        output_root: str | Path,
        export_items: List[Dict[str, Any]],
        generated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        output_root = Path(output_root)
        output_root.mkdir(parents=True, exist_ok=True)

        merged_issues: List[Dict[str, Any]] = []
        for item in export_items:
            issues = item.get("issues")
            if isinstance(issues, list):
                merged_issues.extend(issues)

        merged_issues.sort(
            key=lambda issue: (
                str(issue.get("target_lang", "")),
                str(issue.get("file_name", "")),
                int(issue.get("line_number") or 0),
                str(issue.get("key", "")),
                str(issue.get("error_code", "")),
            )
        )

        return self._write_exports(output_root, merged_issues, generated_at or datetime.now().isoformat(timespec="seconds"))

    def _write_exports(self, output_root: Path, issues: List[Dict[str, Any]], generated_at: str) -> Dict[str, Any]:
        ValidationLogger.save_errors(str(output_root), issues)

        workshop_path = output_root / self.OUTPUT_FILENAME
        payload = {
            "generated_at": generated_at,
            "issue_count": len(issues),
            "issues": issues,
        }
        with open(workshop_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        return {
            "issues_path": str(workshop_path),
            "sidecar_path": str(output_root / ValidationLogger.FILENAME),
            "issue_count": len(issues),
        }

    def _matches_target_language(self, translated_file: Path, target_paradox: str) -> bool:
        lower_name = translated_file.name.lower()
        if lower_name.endswith(f"_l_{target_paradox.lower()}.yml"):
            return True
        return target_paradox.lower() in {part.lower() for part in translated_file.parts}

    def _resolve_source_file(
        self,
        translated_file: Path,
        output_root: Path,
        source_root: Path,
        source_paradox: str,
        target_paradox: str,
    ) -> Optional[Path]:
        try:
            rel_parts = list(translated_file.relative_to(output_root).parts)
        except Exception:
            rel_parts = list(translated_file.parts)

        for index, part in enumerate(rel_parts[:-1]):
            if part.lower() == target_paradox.lower():
                rel_parts[index] = source_paradox

        rel_parts[-1] = re.sub(
            rf"(?P<prefix>[_\s])l_{re.escape(target_paradox)}(?=\.yml$)",
            rf"\g<prefix>l_{source_paradox}",
            rel_parts[-1],
            flags=re.IGNORECASE,
        )

        candidate = source_root.joinpath(*rel_parts)
        if candidate.exists():
            return candidate

        expected_name = Path(rel_parts[-1]).name.lower()
        for found in source_root.rglob(Path(rel_parts[-1]).name):
            if found.name.lower() == expected_name:
                return found
        return None

    def _load_source_entries(self, source_file: Optional[Path]) -> Dict[str, str]:
        if not source_file or not source_file.exists():
            return {}
        try:
            return dict(parse_loc_file(source_file))
        except Exception as exc:
            logger.error(f"Failed to parse source file {source_file}: {exc}")
            return {}

    def _lookup_source_value(self, source_entries: Dict[str, str], key: str) -> str:
        if key in source_entries:
            return source_entries[key]
        base_key = key.split(":")[0]
        if base_key in source_entries:
            return source_entries[base_key]
        with_colon = f"{base_key}:0"
        return source_entries.get(with_colon, "")

    def _resolve_source_context(
        self,
        source_entries: Dict[str, str],
        key: str,
        source_file: Optional[Path],
        source_root: Path,
        translated_file: Path,
        project_name: str,
        project_id: str,
    ) -> Dict[str, str]:
        source_value = self._lookup_source_value(source_entries, key)
        if source_value:
            return {
                "source_str": source_value,
                "status": "found",
                "origin": "source_file",
                "warning": "",
            }

        rel_source_path = ""
        if source_file and source_file.exists():
            try:
                rel_source_path = self._normalize_relpath(source_file.relative_to(source_root))
            except Exception:
                rel_source_path = self._normalize_relpath(source_file)
        else:
            try:
                rel_source_path = self._normalize_relpath(translated_file.relative_to(source_root))
            except Exception:
                rel_source_path = self._normalize_relpath(translated_file.name)

        archived_source = archive_manager.get_source_entry(
            mod_name=project_name or source_root.name,
            project_id=project_id or None,
            file_path=rel_source_path,
            entry_key=key,
        )
        if archived_source and archived_source.get("original"):
            return {
                "source_str": archived_source["original"],
                "status": "fallback_found",
                "origin": "archive_database",
                "warning": "Original source text was recovered from the archive database because it was not found in the current source tree.",
            }

        return {
            "source_str": "",
            "status": "missing",
            "origin": "none",
            "warning": "Original source text was not found in the current source tree or archive database. The fix is generated without source context.",
        }

    def _normalize_relpath(self, rel_path: os.PathLike[str] | str) -> str:
        return str(rel_path).replace("\\", "/")
