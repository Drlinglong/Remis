"""Read-only Agent previews for non-Paradox game outputs."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from scripts.core.game_adapters.workflow_bridge import MANIFEST, safe_output


SUPPORTED_GAME_IDS = frozenset({"project_zomboid", "rimworld", "surviving_mars"})
STRUCTURED_GAME_IDS = frozenset({"project_zomboid", "rimworld"})


class AgentGameOutputError(Exception):
    """A deliberate Agent output boundary error, ready for router mapping."""

    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def as_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def guard_deployment(game_id: str, requested_game_id: str | None = None) -> None:
    """Reject client game overrides and deployment for non-Paradox games."""
    authoritative = str(game_id or "")
    requested = str(requested_game_id or authoritative)
    if requested != authoritative:
        raise AgentGameOutputError(
            "game_id_mismatch", "The requested game does not match the project's configured game.", 400,
        )
    if authoritative in SUPPORTED_GAME_IDS:
        raise AgentGameOutputError(
            "unsupported_game_deployment",
            f"Agent deployment is not supported for {authoritative}; inspect or install the local output manually.",
            409,
        )


def filter_game_actions(game_id: str, actions: Iterable[str], has_output: bool = False) -> list[str]:
    """Remove deployment for these games while preserving review and repair."""
    result = list(actions)
    if game_id not in SUPPORTED_GAME_IDS:
        return result
    result = [action for action in result if action != "approve_export"]
    if has_output and "inspect_local_output" not in result:
        result.append("inspect_local_output")
    return result


def preview_game_output(
    project: dict,
    output_paths: list[str | Path],
    *,
    destination_root: Path,
) -> dict:
    """Describe existing local artifacts without copying or deploying them.

    ``output_paths`` must be the job-scoped paths selected by the Agent export
    candidate resolver. The project game id is authoritative.
    """
    game_id = str(project.get("game_id") or "")
    if game_id not in SUPPORTED_GAME_IDS:
        raise AgentGameOutputError("unsupported_game", "This preview only handles registered non-Paradox games.", 400)
    root = Path(destination_root).resolve()
    candidates = [_contained_existing_root(item, root) for item in output_paths]
    candidates = [item for item in candidates if item is not None]
    if game_id == "surviving_mars":
        local_files = _mars_files(candidates)
        project_id = project.get("project_id") or project.get("id")
        package_url = f"/api/agent/projects/{quote(str(project_id), safe='')}/translation-package"
        return {
            "game_id": game_id,
            "export_mode": "local_files",
            "local_files": local_files,
            "ready": bool(local_files),
            "runtime_verified": False,
            "validation_scope": "artifact_presence_only",
            "target_path": None,
            "requires_approval": False,
            "allowed_actions": ["inspect_local_output"] if local_files else [],
            **({"translation_package": {"supported": True, "options_url": package_url + "/options",
                                        "plan_url": package_url + "/plan"}} if project_id else {}),
        }

    packages = _structured_packages(game_id, candidates)
    return {
        "game_id": game_id,
        "export_mode": "manual_install",
        "packages": packages,
        "ready": bool(packages),
        "runtime_verified": False,
        "validation_scope": "artifact_presence_only",
        "target_path": None,
        "requires_approval": False,
        "allowed_actions": ["inspect_local_output"] if packages else [],
        "diagnostics": [] if packages else [{
            "code": "local_package_manifest_missing",
            "message": "No existing output package with a valid localization manifest was found.",
        }],
    }


def _contained_existing_root(candidate: str | Path, allowed_root: Path) -> Path | None:
    path = Path(candidate)
    if _is_reparse(path):
        return None
    try:
        resolved = path.resolve(strict=True)
        if resolved == allowed_root or not resolved.is_relative_to(allowed_root) or not resolved.is_dir():
            return None
        relative = resolved.relative_to(allowed_root)
        current = allowed_root
        for part in relative.parts:
            current = current / part
            if _is_reparse(current):
                return None
        return resolved
    except (OSError, ValueError):
        return None


def _is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if is_junction and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(reparse_flag and attributes & reparse_flag)
    except OSError:
        return True


def _walk_without_links(root: Path):
    for directory, names, files in os.walk(root, followlinks=False):
        base = Path(directory)
        names[:] = [name for name in names if not _is_reparse(base / name)]
        if _is_reparse(base):
            names[:] = []
            continue
        for name in files:
            path = base / name
            if not _is_reparse(path):
                yield path


def _structured_packages(game_id: str, roots: list[Path]) -> list[dict]:
    packages = []
    seen = set()
    for package_root in roots:
        for manifest_path in _walk_without_links(package_root):
            if manifest_path.name != MANIFEST:
                continue
            manifest_root = manifest_path.parent.resolve()
            identity = (str(manifest_root).casefold(), game_id)
            if identity in seen:
                continue
            seen.add(identity)
            package = _read_manifest_package(manifest_path, manifest_root, game_id)
            packages.extend(package)
    return packages


def _read_manifest_package(manifest_path: Path, package_root: Path, game_id: str) -> list[dict]:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict):
        return []
    if data.get("game_id") != game_id or not isinstance(data.get("files"), dict):
        return []
    source_mod_id = str(data.get("source_mod_id") or "").strip()
    if not source_mod_id:
        return []
    if not _has_required_mod_metadata(package_root, game_id):
        return []
    by_language: dict[str, list[str]] = {}
    recorded_resources = 0
    for relative, record in data["files"].items():
        if not isinstance(relative, str) or not isinstance(record, dict):
            return []
        try:
            path = safe_output(package_root, relative)
            if not path.is_file() or _path_has_reparse(package_root, Path(relative)):
                return []
            language = str(record.get("language") or "").strip()
            if not language:
                return []
            by_language.setdefault(language, []).append(Path(relative).as_posix())
            recorded_resources += 1
        except (OSError, ValueError):
            return []
    if not recorded_resources:
        return []
    return [{
        "package_root": str(package_root),
        "language": language,
        "source_mod_id": source_mod_id,
        "resources": sorted(resources),
        "runtime_verified": False,
        "export_mode": "manual_install",
        "target_path": None,
        "requires_approval": False,
    } for language, resources in sorted(by_language.items())]


def _path_has_reparse(root: Path, relative: Path) -> bool:
    if relative.is_absolute() or ".." in relative.parts:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        if _is_reparse(current):
            return True
    return False


def _has_required_mod_metadata(package_root: Path, game_id: str) -> bool:
    candidates = (("About/About.xml",) if game_id == "rimworld"
                  else ("mod.info", "common/mod.info"))
    for relative in candidates:
        try:
            metadata = safe_output(package_root, relative)
            if _path_has_reparse(package_root, Path(relative)):
                continue
            if metadata.is_file() and metadata.stat().st_size > 0:
                return True
        except (OSError, ValueError):
            continue
    return False


def _mars_files(roots: list[Path]) -> list[str]:
    from scripts.core import surviving_mars_csv
    files = []
    for root in roots:
        for path in _walk_without_links(root):
            if not path.is_file() or not surviving_mars_csv.is_table_file(path):
                continue
            try:
                surviving_mars_csv.parse_file(path)
            except (OSError, ValueError):
                continue
            files.append(str(path.resolve()))
    return sorted(set(files))


def approve_game_output(project: dict, requested_game_id: str | None = None) -> None:
    """Compatibility helper used by routers to fail closed before deployment."""
    guard_deployment(str(project.get("game_id") or ""), requested_game_id)
