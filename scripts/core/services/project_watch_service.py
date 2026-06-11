import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.app_settings import GAME_PROFILES_BY_ID
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.repositories.project_watch_repository import ProjectWatchRepository


LOCALIZATION_DIR_NAMES = {"localization", "localisation"}
LOCALIZATION_EXTENSIONS = {".yml", ".yaml", ".csv", ".txt"}


class ProjectWatchService:
    def __init__(
        self,
        watch_repository: Optional[ProjectWatchRepository] = None,
        project_repository: Optional[ProjectRepository] = None,
    ):
        self.repository = watch_repository or ProjectWatchRepository()
        self.project_repository = project_repository or ProjectRepository()

    async def list_watches(self) -> List[Dict[str, Any]]:
        watches = await self.repository.list_watches()
        return [watch.model_dump() for watch in watches]

    async def create_watch(self, data: Dict[str, Any]) -> Dict[str, Any]:
        path = self._validate_path(data.get("path"))
        if data.get("project_id"):
            project = await self.project_repository.get_project(data["project_id"])
            if not project:
                raise ValueError(f"Project not found: {data['project_id']}")
        watch = await self.repository.create_watch({**data, "path": str(path)})
        return watch.model_dump()

    async def update_watch(self, watch_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        nullable_fields = {"project_id", "scan_interval_minutes"}
        payload = {
            key: value
            for key, value in data.items()
            if value is not None or key in nullable_fields
        }
        if "path" in payload:
            payload["path"] = str(self._validate_path(payload["path"]))
        if payload.get("project_id"):
            project = await self.project_repository.get_project(payload["project_id"])
            if not project:
                raise ValueError(f"Project not found: {payload['project_id']}")
        watch = await self.repository.update_watch(watch_id, payload)
        if not watch:
            raise ValueError(f"Watch not found: {watch_id}")
        return watch.model_dump()

    async def delete_watch(self, watch_id: str) -> None:
        await self.repository.delete_watch(watch_id)

    async def scan_watch(self, watch_id: str) -> Dict[str, Any]:
        watch = await self.repository.get_watch(watch_id)
        if not watch:
            raise ValueError(f"Watch not found: {watch_id}")
        return await self._scan_watch_record(watch)

    async def scan_watches(self, watch_ids: List[str]) -> List[Dict[str, Any]]:
        results = []
        for watch_id in watch_ids:
            results.append(await self.scan_watch(watch_id))
        return results

    async def scan_due_watches(self) -> List[Dict[str, Any]]:
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)
        due = []
        for watch in await self.repository.list_watches():
            if not watch.enabled or not watch.scan_interval_minutes:
                continue
            if not watch.last_scan_at:
                due.append(watch.watch_id)
                continue
            try:
                last_scan = datetime.datetime.fromisoformat(watch.last_scan_at)
                if last_scan.tzinfo is None:
                    last_scan = last_scan.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                due.append(watch.watch_id)
                continue
            age_minutes = (now - last_scan).total_seconds() / 60
            if age_minutes >= watch.scan_interval_minutes:
                due.append(watch.watch_id)
        return await self.scan_watches(due)

    def _validate_path(self, raw_path: Optional[str]) -> Path:
        if not raw_path:
            raise ValueError("Path is required")
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Path not found or not a directory: {raw_path}")
        return path

    async def _scan_watch_record(self, watch) -> Dict[str, Any]:
        root = self._validate_path(watch.path)
        current = self._collect_localization_snapshots(root, watch.project_id)
        previous = {
            snapshot.relative_path: snapshot
            for snapshot in await self.repository.get_snapshots(watch.watch_id)
        }
        previous_summary = watch.last_scan_summary if isinstance(watch.last_scan_summary, dict) else {}
        has_pending_change = (
            watch.status == "changed"
            and int(previous_summary.get("changed_count", 0) or 0) > 0
        )
        baseline_created = len(previous) == 0 and len(current) > 0
        no_localization_files = len(current) == 0

        added = []
        modified = []
        deleted = []
        current_by_path = {item["relative_path"]: item for item in current}

        if not baseline_created:
            for rel_path, item in current_by_path.items():
                old = previous.get(rel_path)
                if not old:
                    added.append(self._public_snapshot(item))
                elif old.sha256 != item["sha256"]:
                    modified.append({
                        **self._public_snapshot(item),
                        "previous_sha256": old.sha256,
                    })

            for rel_path, old in previous.items():
                if rel_path not in current_by_path:
                    deleted.append({
                        "relative_path": rel_path,
                        "sha256": old.sha256,
                        "size": old.size,
                        "mtime_ns": old.mtime_ns,
                    })

        changed = bool(added or modified or deleted)
        status = "changed" if changed else "clean"
        if no_localization_files:
            status = "no_localization"
        elif baseline_created:
            status = "baseline"

        summary = {
            "watch_id": watch.watch_id,
            "status": status,
            "baseline_created": baseline_created,
            "root_path": str(root),
            "scanned_file_count": len(current),
            "added_count": len(added),
            "modified_count": len(modified),
            "deleted_count": len(deleted),
            "changed_count": len(added) + len(modified) + len(deleted),
            "added": added,
            "modified": modified,
            "deleted": deleted,
        }
        if not changed and has_pending_change:
            status = "changed"
            summary = {
                **previous_summary,
                "watch_id": watch.watch_id,
                "status": "changed",
                "baseline_created": False,
                "root_path": str(root),
                "scanned_file_count": len(current),
                "pending_acknowledgement": True,
            }
        await self.repository.replace_snapshots_and_update_watch(
            watch.watch_id,
            current,
            summary,
            status,
            changed,
        )
        return summary

    def _collect_localization_snapshots(self, root: Path, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        roots = self._localization_roots(root, project_id)
        snapshots = []
        seen = set()
        for loc_root in roots:
            for path in loc_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in LOCALIZATION_EXTENSIONS:
                    continue
                if any(part.startswith(".") for part in path.relative_to(root).parts):
                    continue
                rel_path = path.relative_to(root).as_posix()
                if rel_path in seen:
                    continue
                seen.add(rel_path)
                stat = path.stat()
                snapshots.append({
                    "relative_path": rel_path,
                    "sha256": self._sha256(path),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                })
        snapshots.sort(key=lambda item: item["relative_path"])
        return snapshots

    def _localization_roots(self, root: Path, project_id: Optional[str] = None) -> List[Path]:
        candidates: List[Path] = []
        if root.name.lower() in LOCALIZATION_DIR_NAMES:
            candidates.append(root)

        for name in LOCALIZATION_DIR_NAMES:
            child = root / name
            if child.exists() and child.is_dir():
                candidates.append(child)

        for profile in GAME_PROFILES_BY_ID.values():
            source_folder = profile.get("source_localization_folder")
            if source_folder:
                child = root / str(source_folder)
                if child.exists() and child.is_dir():
                    candidates.append(child)

        for child in root.rglob("*"):
            if child.is_dir() and child.name.lower() in LOCALIZATION_DIR_NAMES:
                candidates.append(child)

        unique = []
        seen = set()
        for candidate in candidates:
            key = str(candidate.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _public_snapshot(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "relative_path": item["relative_path"],
            "sha256": item["sha256"],
            "size": item["size"],
            "mtime_ns": item["mtime_ns"],
        }
