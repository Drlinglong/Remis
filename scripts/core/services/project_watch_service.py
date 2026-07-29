import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from scripts.app_settings import GAME_PROFILES_BY_ID
from scripts.core.repositories.project_repository import ProjectRepository
from scripts.core.repositories.project_watch_repository import ProjectWatchRepository
from scripts.shared import task_state


LOCALIZATION_DIR_NAMES = {"localization", "localisation"}
LOCALIZATION_EXTENSIONS = {".yml", ".yaml", ".csv", ".txt"}


class ProjectWatchService:
    def __init__(
        self,
        watch_repository: Optional[ProjectWatchRepository] = None,
        project_repository: Optional[ProjectRepository] = None,
        task_ledger=task_state,
    ):
        self.repository = watch_repository or ProjectWatchRepository()
        self.project_repository = project_repository or ProjectRepository()
        self.task_ledger = task_ledger

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
        return await self._scan_watch_task(
            watch,
            created_by={"type": "user"},
            scheduled=False,
            suppress_errors=False,
        )

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
                due.append(watch)
                continue
            try:
                last_scan = datetime.datetime.fromisoformat(watch.last_scan_at)
                if last_scan.tzinfo is None:
                    last_scan = last_scan.replace(tzinfo=datetime.timezone.utc)
            except ValueError:
                due.append(watch)
                continue
            age_minutes = (now - last_scan).total_seconds() / 60
            if age_minutes >= watch.scan_interval_minutes:
                due.append(watch)
        return [
            await self._scan_watch_task(
                watch,
                created_by={
                    "type": "automation",
                    "actor_id": "project_watch_scheduler",
                    "label": "Automatic monitor",
                },
                scheduled=True,
                suppress_errors=True,
            )
            for watch in due
        ]

    def _validate_path(self, raw_path: Optional[str]) -> Path:
        if not raw_path:
            raise ValueError("Path is required")
        path = Path(raw_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Path not found or not a directory: {raw_path}")
        return path

    async def _scan_watch_task(
        self,
        watch,
        *,
        created_by: Dict[str, Any],
        scheduled: bool,
        suppress_errors: bool,
    ) -> Dict[str, Any]:
        task_id = str(uuid.uuid4())
        project = (
            await self.project_repository.get_project(watch.project_id)
            if watch.project_id
            else None
        )
        project_data = (
            project.model_dump()
            if project is not None and hasattr(project, "model_dump")
            else (project or {})
        )
        project_context = {
            "name": project_data.get("name") or watch.name,
            "game_id": project_data.get("game_id"),
        }
        shared_operation_key = (
            f"project_translation_write:{watch.project_id}"
            if watch.project_id
            else f"project_watch_scan:{watch.watch_id}"
        )
        task_fields = {
            "kind": "project_watch_scan",
            "project_id": watch.project_id,
            "project_context": project_context,
            "title": (
                f"Scheduled update check for {watch.name}"
                if scheduled
                else f"Scan updates for {watch.name}"
            ),
            "source_route": "/project-tracking",
            "created_by": created_by,
            "blocking": True,
            "blocking_reason": (
                "Remis is taking a consistent project snapshot. Conflicting project writes "
                "are blocked until this scan finishes."
            ),
        }
        try:
            self.task_ledger.create_task(
                task_id,
                status="running",
                log_message=(
                    f"Scheduled scan started for {watch.name}."
                    if scheduled
                    else f"Manual scan started for {watch.name}."
                ),
                fields=task_fields,
                dedupe_key=shared_operation_key,
                reject_duplicate=True,
            )
        except self.task_ledger.DuplicateTaskError as exc:
            existing_task_id = exc.existing_task.get("task_id")
            conflict_message = (
                f"{'Scheduled' if scheduled else 'Manual'} scan was blocked because "
                "another task is already reading or writing this project."
            )
            self.task_ledger.create_task(
                task_id,
                status="failed",
                log_message=conflict_message,
                fields={
                    **task_fields,
                    "blocking": False,
                    "blocking_reason": conflict_message,
                    "attention_reason": conflict_message,
                    "result": {
                        "types": ["project_watch_scan"],
                        "summary": conflict_message,
                        "metadata": {
                            "watch_id": watch.watch_id,
                            "scan_status": "blocked",
                            "conflicting_task_id": existing_task_id,
                        },
                    },
                },
            )
            return {
                "watch_id": watch.watch_id,
                "status": "blocked",
                "task_id": task_id,
                "conflicting_task_id": existing_task_id,
                "changed_count": 0,
                "message": conflict_message,
            }

        try:
            summary = await self._scan_watch_record(watch, task_id=task_id)
            changed_count = int(summary.get("changed_count", 0) or 0)
            result_summary = (
                f"Scan completed with {changed_count} localization change(s)."
            )
            self.task_ledger.update_task(
                task_id,
                status="completed",
                append_log=result_summary,
                progress={"current": 1, "total": 1, "percent": 100, "stage": "Completed"},
                fields={
                    "result": {
                        "types": ["project_watch_scan"],
                        "summary": result_summary,
                        "metadata": {
                            **summary,
                            "watch_name": watch.name,
                        },
                    },
                    "checkpoint": {
                        "available": False,
                        "resume_supported": False,
                        "stage": "Completed",
                    },
                },
            )
            return summary
        except Exception as exc:
            failure_message = (
                f"{'Scheduled' if scheduled else 'Manual'} project scan failed. "
                "Check the task diagnostics."
            )
            self.task_ledger.update_task(
                task_id,
                status="failed",
                message=failure_message,
                append_log=failure_message,
                fields={
                    "attention_reason": failure_message,
                    "result": {
                        "types": ["project_watch_scan"],
                        "summary": failure_message,
                        "metadata": {
                            "watch_id": watch.watch_id,
                            "scan_status": "failed",
                        },
                    },
                },
            )
            self.task_ledger.append_task_event(
                task_id,
                repr(exc),
                audience="diagnostic",
                level="error",
                event_type="exception",
            )
            if not suppress_errors:
                raise
            return {
                "watch_id": watch.watch_id,
                "status": "failed",
                "task_id": task_id,
                "changed_count": 0,
                "message": failure_message,
            }

    async def _scan_watch_record(self, watch, task_id: Optional[str] = None) -> Dict[str, Any]:
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

        if no_localization_files:
            if has_pending_change:
                summary = {
                    **previous_summary,
                    "watch_id": watch.watch_id,
                    "status": "changed",
                    "baseline_created": False,
                    "root_path": str(root),
                    "scanned_file_count": 0,
                    "snapshot_preserved": bool(previous),
                    "pending_acknowledgement": True,
                    "scan_warning": "no_localization",
                }
                status = "changed"
            else:
                summary = {
                    "watch_id": watch.watch_id,
                    "status": "no_localization",
                    "baseline_created": False,
                    "root_path": str(root),
                    "scanned_file_count": 0,
                    "added_count": 0,
                    "modified_count": 0,
                    "deleted_count": 0,
                    "changed_count": 0,
                    "added": [],
                    "modified": [],
                    "deleted": [],
                    "snapshot_preserved": bool(previous),
                }
                status = "no_localization"
            await self.repository.replace_snapshots_and_update_watch(
                watch.watch_id,
                current,
                summary,
                status,
                False,
                replace_snapshots=False,
            )
            return summary

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
        if baseline_created:
            status = "baseline"

        summary = {
            "watch_id": watch.watch_id,
            "task_id": task_id,
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
                "task_id": task_id,
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
