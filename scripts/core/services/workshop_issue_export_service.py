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
from scripts.core.vic3_country_adjective_context import is_country_adj_reference
from scripts.utils.validation_logger import ValidationLogger

logger = logging.getLogger(__name__)

VIC3_ADJ_REFERENCE_REVIEW_CODE = "vic3_country_adjective_reference_review"


def _vic3_reference_review_issue(
    *,
    game_id: str,
    source_value: str,
    base_issue: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Create a non-repairable review signal without changing validator results."""

    if game_id != "victoria3" or not is_country_adj_reference(source_value):
        return None
    return {
        **base_issue,
        "error_type": VIC3_ADJ_REFERENCE_REVIEW_CODE,
        "error_code": VIC3_ADJ_REFERENCE_REVIEW_CODE,
        "details": (
            "Review the target-language grammar around the preserved country "
            "adjective runtime token. The token must remain intact, but its "
            "surrounding word order, particles, or inflection may need review."
        ),
        "details_code": VIC3_ADJ_REFERENCE_REVIEW_CODE,
        "details_params": {},
        "severity": "human_review",
        "requires_human_review": True,
    }


def _base_issue(
    *,
    translated_file: Path,
    rel_output_path: str,
    source_file: Optional[Path],
    source_root: Path,
    key: str,
    line_number: int,
    source_value: str,
    source_lookup: Dict[str, Any],
    target_value: str,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "file_name": rel_output_path,
        "file_path": str(translated_file),
        "source_file": (
            str(source_file.relative_to(source_root)).replace("\\", "/")
            if source_file and source_file.exists()
            else ""
        ),
        "key": key,
        "line_number": line_number,
        "source_str": source_value,
        "source_context_status": source_lookup["status"],
        "source_context_origin": source_lookup["origin"],
        "source_context_warning": source_lookup.get("warning", ""),
        "target_str": target_value,
        "status": "detected",
        "text_sample": target_value[:100],
        **metadata,
    }


def _issue_metadata(
    *,
    workflow: str,
    project_id: str,
    run_id: str,
    source_version_id: Optional[int],
    game_id: str,
    project_name: str,
    target_lang: str,
    generated_at: str,
) -> Dict[str, Any]:
    return {
        "workflow": workflow,
        "project_id": project_id,
        "run_id": run_id,
        "source_version_id": source_version_id,
        "game_id": game_id,
        "project_name": project_name,
        "target_lang": target_lang,
        "generated_at": generated_at,
    }


def _validator_issue(base_issue: Dict[str, Any], result: Any, value: str):
    return {
        **base_issue,
        "line_number": result.line_number,
        "error_type": result.message,
        "error_code": result.code or result.message,
        "details": result.details or "",
        "details_code": result.details_code or "",
        "details_params": result.details_params or {},
        "severity": result.level.value,
        "text_sample": result.text_sample or value[:100],
    }


def resolve_dynamic_valid_tags(game_profile: Dict[str, Any], source_root: str | Path) -> Optional[List[str]]:
    official_tags_path = game_profile.get("official_tags_codex")
    if not official_tags_path:
        return None

    try:
        from scripts.utils import tag_scanner

        source_root = Path(source_root)
        loc_folder = game_profile.get("source_localization_folder", "localization")
        return tag_scanner.analyze_mod_and_get_all_valid_tags(
            mod_loc_path=str(source_root / loc_folder),
            official_tags_json_path=official_tags_path,
        )
    except Exception as exc:
        logger.warning("Failed to resolve dynamic validation tags for %s: %s", game_profile.get("id"), exc)
        return None


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
        run_id: str = "",
        source_version_id: Optional[int] = None,
        dynamic_valid_tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        output_root = Path(output_root)
        source_root = Path(source_root)
        output_root.mkdir(parents=True, exist_ok=True)

        generated_at = datetime.now().isoformat(timespec="seconds")
        issues: List[Dict[str, Any]] = []
        target_paradox = iso_to_paradox(target_lang_info.get("code", ""))
        source_paradox = iso_to_paradox(source_lang_info.get("code", ""))
        game_id = game_profile.get("id", "")
        issue_metadata = _issue_metadata(
            workflow=workflow,
            project_id=project_id,
            run_id=run_id,
            source_version_id=source_version_id,
            game_id=game_id,
            project_name=project_name,
            target_lang=target_lang_info.get("code", ""),
            generated_at=generated_at,
        )

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
                base_issue = _base_issue(
                    translated_file=translated_file,
                    rel_output_path=rel_output_path,
                    source_file=source_file,
                    source_root=source_root,
                    key=key,
                    line_number=line_number,
                    source_value=source_value,
                    source_lookup=source_lookup,
                    target_value=value,
                    metadata=issue_metadata,
                )
                try:
                    results = self.validator.validate_entry(
                        game_id=game_id,
                        key=key,
                        value=value,
                        line_number=line_number,
                        source_lang=source_lang_info,
                        source_value=source_value,
                        target_lang=target_lang_info.get("code"),
                        dynamic_valid_tags=dynamic_valid_tags,
                    )
                except Exception as exc:
                    logger.error(f"Failed to validate {translated_file} [{key}]: {exc}")
                    continue

                for result in results:
                    if result.level.value not in {"error", "warning"}:
                        continue
                    issues.append(_validator_issue(base_issue, result, value))

                review_issue = _vic3_reference_review_issue(
                    game_id=game_id,
                    source_value=source_value,
                    base_issue=base_issue,
                )
                if review_issue:
                    issues.append(review_issue)

        export_result = self._write_exports(
            output_root,
            issues,
            generated_at,
            project_id=project_id,
            run_id=run_id,
            source_version_id=source_version_id,
        )
        export_result["issue_count"] = len(issues)
        export_result["issues"] = issues
        return export_result

    def merge_exports(
        self,
        output_root: str | Path,
        export_items: List[Dict[str, Any]],
        generated_at: Optional[str] = None,
        project_id: str = "",
        run_id: str = "",
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

        source_version_ids = {
            item.get("source_version_id")
            for item in export_items
            if item.get("source_version_id") is not None
        }
        language_source_versions = {
            str(item.get("target_lang")): item.get("source_version_id")
            for item in export_items
            if item.get("target_lang") and item.get("source_version_id") is not None
        }
        source_version_id = next(iter(source_version_ids)) if len(source_version_ids) == 1 else None

        return self._write_exports(
            output_root,
            merged_issues,
            generated_at or datetime.now().isoformat(timespec="seconds"),
            project_id=project_id,
            run_id=run_id,
            source_version_id=source_version_id,
            source_version_ids=sorted(source_version_ids),
            language_source_versions=language_source_versions,
        )

    def update_export_metadata(
        self,
        output_root: str | Path,
        *,
        project_id: str = "",
        run_id: str = "",
        source_version_id: Optional[int] = None,
        source_version_ids: Optional[List[int]] = None,
        language_source_versions: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        output_root = Path(output_root)
        workshop_path = output_root / self.OUTPUT_FILENAME
        issues = self._load_existing_issues(workshop_path)
        generated_at = datetime.now().isoformat(timespec="seconds")
        return self._write_exports(
            output_root,
            issues,
            generated_at,
            project_id=project_id,
            run_id=run_id,
            source_version_id=source_version_id,
            source_version_ids=source_version_ids,
            language_source_versions=language_source_versions,
        )

    def write_issues(
        self,
        output_root: str | Path,
        issues: List[Dict[str, Any]],
        *,
        project_id: str = "",
        run_id: str = "",
        source_version_id: Optional[int] = None,
        source_version_ids: Optional[List[int]] = None,
        language_source_versions: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        return self._write_exports(
            Path(output_root),
            issues,
            datetime.now().isoformat(timespec="seconds"),
            project_id=project_id,
            run_id=run_id,
            source_version_id=source_version_id,
            source_version_ids=source_version_ids,
            language_source_versions=language_source_versions,
        )

    def _write_exports(
        self,
        output_root: Path,
        issues: List[Dict[str, Any]],
        generated_at: str,
        *,
        project_id: str = "",
        run_id: str = "",
        source_version_id: Optional[int] = None,
        source_version_ids: Optional[List[int]] = None,
        language_source_versions: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        metadata = {
            "project_id": project_id,
            "run_id": run_id,
            "source_version_id": source_version_id,
            "source_version_ids": source_version_ids or ([] if source_version_id is None else [source_version_id]),
            "language_source_versions": language_source_versions or {},
        }
        issues = [
            {
                **issue,
                **{key: value for key, value in metadata.items() if value not in ("", None, [], {})},
            }
            for issue in issues
        ]
        ValidationLogger.save_errors(str(output_root), issues)

        workshop_path = output_root / self.OUTPUT_FILENAME
        payload = {
            "generated_at": generated_at,
            "issue_count": len(issues),
            **{key: value for key, value in metadata.items() if value not in ("", None, [], {})},
            "issues": issues,
        }
        with open(workshop_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        return {
            "issues_path": str(workshop_path),
            "sidecar_path": str(output_root / ValidationLogger.FILENAME),
            "issue_count": len(issues),
            **{key: value for key, value in metadata.items() if value not in ("", None, [], {})},
        }

    def _load_existing_issues(self, workshop_path: Path) -> List[Dict[str, Any]]:
        try:
            payload = json.loads(workshop_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        return [issue for issue in issues if isinstance(issue, dict)]

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
