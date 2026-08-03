import logging
from pathlib import Path
from typing import Any, Dict, Optional

from scripts.core.loc_parser import parse_loc_file
from scripts.core.paradox_localization_parser import parse_text, patch_text
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.utils.post_process_validator import PostProcessValidator

logger = logging.getLogger(__name__)

INVALID_KEY_ERROR_CODE = "validation_invalid_key_format"


def is_repairable_workshop_issue(issue: Dict[str, Any]) -> bool:
    error_code = str(issue.get("error_code") or "").strip()
    error_type = str(issue.get("error_type") or "").strip()
    return INVALID_KEY_ERROR_CODE not in {error_code, error_type}


def _is_within(candidate: Path, root: Path) -> bool:
    return candidate == root or root in candidate.parents


def _resolve_existing_candidate(candidate: Path, allowed_roots: list[Path]) -> Optional[Path]:
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if any(_is_within(resolved, root) for root in allowed_roots) else None


def _registered_translation_roots(project: Dict[str, Any]) -> list[Path]:
    source_path = project.get("source_path")
    if not source_path:
        return []

    source_root = Path(source_path)
    translation_dirs = ProjectJsonManager(source_path).get_config().get("translation_dirs", []) or []
    roots: list[Path] = []
    for configured_path in translation_dirs:
        root = Path(configured_path)
        if not root.is_absolute():
            root = source_root / root
        try:
            roots.append(root.resolve(strict=True))
        except (OSError, RuntimeError):
            continue
    return roots


def resolve_project_translation_target(
    project: Dict[str, Any],
    issue_file_path: Optional[str],
    issue_file_name: Optional[str],
) -> Optional[Path]:
    allowed_roots = _registered_translation_roots(project)
    if not allowed_roots:
        return None

    if issue_file_path:
        resolved = _resolve_existing_candidate(Path(issue_file_path), allowed_roots)
        if resolved:
            return resolved

    if not issue_file_name:
        return None

    relative_path = Path(issue_file_name)
    if relative_path.is_absolute():
        return None
    for root in allowed_roots:
        resolved = _resolve_existing_candidate(root / relative_path, allowed_roots)
        if resolved:
            return resolved
    return None


def resolve_output_translation_target(
    output_root: str | Path,
    issue: Dict[str, Any],
) -> Optional[Path]:
    try:
        allowed_root = Path(output_root).resolve(strict=True)
    except (OSError, RuntimeError):
        return None

    file_path = issue.get("file_path")
    if file_path:
        resolved = _resolve_existing_candidate(Path(file_path), [allowed_root])
        if resolved:
            return resolved

    file_name = issue.get("file_name")
    if not file_name:
        return None
    relative_path = Path(file_name)
    if relative_path.is_absolute():
        return None
    return _resolve_existing_candidate(allowed_root / relative_path, [allowed_root])


def apply_translation_fix_to_file(file_path: Path, key_to_fix: str, new_value: str) -> bool:
    try:
        with open(file_path, "r", encoding="utf-8-sig", newline="") as handle:
            source_text = handle.read()
        report = parse_text(source_text)
        target = next(
            (
                entry
                for entry in report.eligible_entries
                if entry.key == key_to_fix
                or entry.base_key == key_to_fix.split(":")[0]
            ),
            None,
        )
        if target is None:
            return False
        patched_text = patch_text(source_text, [(target, new_value)])
        with open(file_path, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(patched_text)
        return True
    except Exception as exc:
        logger.error("Failed to apply workshop fix to %s: %s", file_path, exc)
        return False


def _read_translation_value(file_path: Path, key_to_find: str) -> Optional[str]:
    try:
        entries = dict(parse_loc_file(file_path))
    except Exception as exc:
        logger.error("Failed to parse workshop translation file %s: %s", file_path, exc)
        return None

    if key_to_find in entries:
        return entries[key_to_find]
    normalized_key = f"{key_to_find}:0"
    if normalized_key in entries:
        return entries[normalized_key]
    base_key = key_to_find.split(":")[0]
    return entries.get(f"{base_key}:0")


def _validation_errors(
    game_id: str,
    key: str,
    source_str: str,
    target_str: str,
    target_lang: Optional[str],
) -> list[str]:
    try:
        results = PostProcessValidator().validate_entry(
            game_id=game_id,
            key=key,
            value=target_str,
            source_value=source_str,
            target_lang=target_lang,
        )
    except Exception as exc:
        return [f"Post-validation crashed: {exc}"]
    return [result.message for result in results if result.level.value == "error"]


def _restore_file(target_path: Path, original_bytes: bytes) -> bool:
    try:
        target_path.write_bytes(original_bytes)
        return True
    except OSError as exc:
        logger.error("Failed to roll back workshop write to %s: %s", target_path, exc)
        return False


def apply_validated_workshop_fix(
    project: Dict[str, Any],
    game_id: str,
    file_name: str,
    file_path: Optional[str],
    key: str,
    source_str: str,
    suggested_fix: str,
    target_lang: Optional[str] = None,
) -> tuple[bool, str, str]:
    target_path = resolve_project_translation_target(project, file_path, file_name)
    if not target_path:
        return False, "target_not_found", "Target file not found inside a registered translation directory."
    return apply_validated_workshop_fix_to_path(
        target_path=target_path,
        game_id=game_id,
        key=key,
        source_str=source_str,
        suggested_fix=suggested_fix,
        target_lang=target_lang,
    )


def apply_validated_workshop_fix_to_path(
    target_path: Path,
    game_id: str,
    key: str,
    source_str: str,
    suggested_fix: str,
    target_lang: Optional[str] = None,
) -> tuple[bool, str, str]:
    validation_errors = _validation_errors(game_id, key, source_str, suggested_fix, target_lang)
    if validation_errors:
        return False, "pre_validation_failure", "Candidate validation failed: " + " | ".join(validation_errors)

    try:
        original_bytes = target_path.read_bytes()
    except OSError as exc:
        return False, "snapshot_failure", f"Could not snapshot target before write: {exc}"

    if not apply_translation_fix_to_file(target_path, key, suggested_fix):
        restored = _restore_file(target_path, original_bytes)
        reason = "writeback_failure" if restored else "rollback_failure"
        return False, reason, "Failed to write suggested fix; original file was restored." if restored else "Write and rollback both failed."

    current_value = _read_translation_value(target_path, key)
    if current_value == suggested_fix:
        validation_errors = _validation_errors(game_id, key, source_str, current_value, target_lang)
        if not validation_errors:
            return True, "validated_and_applied", "Applied and re-validated successfully."
        message = "Post-write validation failed: " + " | ".join(validation_errors)
        failure_reason = "post_validation_failure"
    elif current_value is None:
        message = "Fixed entry could not be read back from target file."
        failure_reason = "readback_missing"
    else:
        message = "Read-back confirmation mismatch after writing fix."
        failure_reason = "readback_mismatch"

    if _restore_file(target_path, original_bytes):
        return False, failure_reason, message + " Original file was restored."
    return False, "rollback_failure", message + " Original file could not be restored."
