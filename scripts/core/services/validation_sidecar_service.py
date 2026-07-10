import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.utils.validation_logger import ValidationLogger

logger = logging.getLogger(__name__)


class ValidationSidecarService:
    CURRENT_VERSION_SCOPE = "current_translation_version"

    @staticmethod
    def attach_project_file_ids(
        issues: List[Dict[str, Any]],
        project_files: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Attach stable project file ids to legacy and current validation issues."""
        normalized_files = []
        for project_file in project_files or []:
            file_path = project_file.get("file_path")
            file_id = project_file.get("file_id")
            if not file_path or not file_id:
                continue
            normalized_files.append((
                str(Path(file_path).resolve(strict=False)).replace("\\", "/").lower(),
                file_id,
            ))

        enriched = []
        for issue in issues or []:
            item = dict(issue)
            if item.get("file_id"):
                enriched.append(item)
                continue
            candidates = [item.get("file_path"), item.get("file_name")]
            matches = set()
            for candidate in filter(None, candidates):
                normalized_candidate = str(candidate).replace("\\", "/").lower().lstrip("./")
                for normalized_path, file_id in normalized_files:
                    if normalized_path == normalized_candidate or normalized_path.endswith(f"/{normalized_candidate}"):
                        matches.add(file_id)
            if len(matches) == 1:
                item["file_id"] = matches.pop()
            enriched.append(item)
        return enriched

    def load_issue_file(self, path: Path) -> List[Dict[str, Any]]:
        payload = self.load_payload(path)
        issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
        return [issue for issue in issues if isinstance(issue, dict)]

    def load_payload(self, path: Path) -> Dict[str, Any] | List[Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read validation sidecar %s: %s", path, exc)
            return {}
        return payload

    def active_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            issue for issue in issues
            if str(issue.get("status", "detected")).lower() not in {"fixed", "ignored"}
        ]

    def issue_counts(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for issue in issues:
            label = issue.get("error_code") or issue.get("error_type") or "unknown"
            counts[label] = counts.get(label, 0) + 1
        return counts

    def list_candidates(self, project_root: str) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []
        seen_paths = set()

        def add_candidate(path: Path, kind: str, root: Optional[Path] = None):
            resolved = str(path.resolve(strict=False)).lower()
            if resolved in seen_paths or not path.exists():
                return
            payload = self.load_payload(path)
            issues = payload.get("issues", []) if isinstance(payload, dict) else payload if isinstance(payload, list) else []
            issues = self.active_issues([issue for issue in issues if isinstance(issue, dict)])
            seen_paths.add(resolved)
            candidates.append({
                "path": str(path),
                "kind": kind,
                "issue_count": len(issues),
                "last_updated_at": self._format_file_mtime(path),
                "project_id": payload.get("project_id") if isinstance(payload, dict) else None,
                "run_id": payload.get("run_id") if isinstance(payload, dict) else None,
                "source_version_id": payload.get("source_version_id") if isinstance(payload, dict) else None,
                "source_version_ids": payload.get("source_version_ids", []) if isinstance(payload, dict) else [],
                "language_source_versions": payload.get("language_source_versions", {}) if isinstance(payload, dict) else {},
                "_root": str(root or path.parent),
                "_version_key": self._version_key(root or path.parent, path, payload),
            })

        source_path = ValidationLogger._get_log_path(project_root)
        add_candidate(source_path, "source", Path(project_root))

        try:
            config = ProjectJsonManager(project_root).get_config()
        except Exception as exc:
            logger.warning("Failed to read project translation dirs for validation status: %s", exc)
            config = {}

        for trans_dir in config.get("translation_dirs", []) or []:
            trans_path = Path(trans_dir)
            add_candidate(trans_path / "workshop_issues.json", "translation", trans_path)
            add_candidate(trans_path / ValidationLogger.FILENAME, "translation", trans_path)

        candidates.sort(key=lambda item: item.get("last_updated_at") or "", reverse=True)
        return candidates

    def load_status(self, project_root: str, selected_sidecar_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
        candidates = self.list_candidates(project_root)
        if not candidates:
            return None

        selected_candidate = self._select_candidate(candidates, selected_sidecar_path)
        selected_kind = selected_candidate.get("kind")

        if selected_kind == "source":
            source_paths = [Path(selected_candidate["path"])]
            scope = "source_sidecar"
        else:
            source_paths = self._current_translation_paths(candidates, selected_candidate)
            scope = self.CURRENT_VERSION_SCOPE

        active_issues = self.active_issues(self._merge_issue_paths(source_paths))

        return {
            "issues": active_issues,
            "issue_type_counts": self.issue_counts(active_issues),
            "sidecar_path": selected_candidate["path"],
            "last_updated_at": selected_candidate.get("last_updated_at"),
            "sidecar_candidates": self._public_candidates(candidates),
            "sidecar_scope": scope,
            "source_paths": [str(path) for path in source_paths],
        }

    def current_translation_issues(self, project_root: str, selected_sidecar_path: Optional[str] = None) -> List[Dict[str, Any]]:
        status = self.load_status(project_root, selected_sidecar_path)
        if not status:
            return []
        return status["issues"]

    def _select_candidate(self, candidates: List[Dict[str, Any]], selected_sidecar_path: Optional[str]) -> Dict[str, Any]:
        if selected_sidecar_path:
            requested = str(Path(selected_sidecar_path).resolve(strict=False)).lower()
            for candidate in candidates:
                if str(Path(candidate["path"]).resolve(strict=False)).lower() == requested:
                    return candidate
            raise HTTPException(status_code=400, detail="Unknown validation sidecar path")

        translation_candidates = [candidate for candidate in candidates if candidate.get("kind") == "translation"]
        if translation_candidates:
            return max(
                translation_candidates,
                key=lambda candidate: (
                    self._version_sort_value(candidate.get("_version_key", "")),
                    candidate.get("last_updated_at") or "",
                    candidate.get("path") or "",
                ),
            )

        return candidates[0]

    def _current_translation_paths(self, candidates: List[Dict[str, Any]], selected_candidate: Dict[str, Any]) -> List[Path]:
        translation_candidates = [candidate for candidate in candidates if candidate.get("kind") == "translation"]
        if not translation_candidates:
            return []

        version_key = selected_candidate.get("_version_key")
        if version_key:
            scoped = [
                candidate for candidate in translation_candidates
                if candidate.get("_version_key") == version_key
            ]
        else:
            scoped = [selected_candidate]

        return [Path(candidate["path"]) for candidate in self._prefer_workshop_sidecars(scoped)]

    def _prefer_workshop_sidecars(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_root: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            root = candidate.get("_root") or str(Path(candidate["path"]).parent)
            previous = by_root.get(root)
            if not previous:
                by_root[root] = candidate
                continue
            if Path(candidate["path"]).name == "workshop_issues.json":
                by_root[root] = candidate

        return sorted(by_root.values(), key=lambda item: item.get("path") or "")

    def _merge_issue_paths(self, paths: List[Path]) -> List[Dict[str, Any]]:
        merged: Dict[tuple, Dict[str, Any]] = {}
        for path in paths:
            for issue in self.load_issue_file(path):
                identity = (
                    str(issue.get("target_lang", "")),
                    str(issue.get("file_name", "")),
                    str(issue.get("key", "")),
                    str(issue.get("error_code") or issue.get("error_type") or ""),
                    str(issue.get("details") or ""),
                    int(issue.get("line_number") or 0),
                )
                if identity not in merged:
                    merged[identity] = issue

        issues = list(merged.values())
        issues.sort(key=lambda item: (
            str(item.get("target_lang", "")),
            str(item.get("file_name", "")),
            int(item.get("line_number") or 0),
            str(item.get("key", "")),
            str(item.get("error_code") or item.get("error_type") or ""),
        ))
        return issues

    def _version_key(self, root: Path, path: Path, payload: Dict[str, Any] | List[Any]) -> str:
        if isinstance(payload, dict):
            project_id = payload.get("project_id") or ""
            run_id = payload.get("run_id") or ""
            source_version_id = payload.get("source_version_id")
            source_version_ids = payload.get("source_version_ids")
            if project_id and source_version_id is not None:
                return f"project-source-version:{project_id}:{source_version_id}"
            if project_id and isinstance(source_version_ids, list) and source_version_ids:
                versions = ",".join(sorted(str(item) for item in source_version_ids))
                return f"project-source-versions:{project_id}:{versions}"

        name_match = re.search(r"incremental-update-(\d{8})", root.name, re.IGNORECASE)
        if name_match:
            return f"folder-date:{name_match.group(1)}"

        if isinstance(payload, dict):
            project_id = payload.get("project_id") or ""
            run_id = payload.get("run_id") or ""
            if project_id and run_id:
                return f"project-run:{project_id}:{run_id}"

        generated_at = payload.get("generated_at") if isinstance(payload, dict) else None
        if isinstance(generated_at, str) and generated_at[:10]:
            return f"generated-date:{generated_at[:10]}"

        try:
            return f"mtime-date:{datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()}"
        except OSError:
            return ""

    def _format_file_mtime(self, path: Path) -> Optional[str]:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        except OSError:
            return None

    def _version_sort_value(self, version_key: str) -> int:
        match = re.search(r"(\d{8})", version_key or "")
        if not match:
            return 0
        return int(match.group(1))

    def _public_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {key: value for key, value in candidate.items() if not key.startswith("_")}
            for candidate in candidates
        ]
