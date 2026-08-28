"""Maintenance workflow for persistent vanilla reference libraries."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import threading
import uuid
from typing import Callable, Optional

from scripts.app_settings import GAME_PROFILES, GAME_PROFILES_BY_ID
from scripts.core.services.paradox_installation_discovery import (
    discover_paradox_localizations,
    official_localization_roots,
)
from scripts.core.services.vanilla_reference_service import VanillaReferenceService
from scripts.shared import task_state


REFERENCE_LIBRARY_TASK_KIND = "reference_library_maintenance"
REFERENCE_LIBRARY_DEDUPE_KEY = "reference-library-maintenance"
_REFERENCE_WRITE_LOCK = threading.Lock()


class ReferenceLibraryService:
    def __init__(self, reference_service: VanillaReferenceService | None = None) -> None:
        self.reference_service = reference_service or VanillaReferenceService()

    def status(self) -> dict:
        active = {item.game_id: item for item in self.reference_service.list_active_indexes()}
        libraries = []
        for profile in GAME_PROFILES.values():
            game_id = profile["id"]
            info = active.get(game_id)
            libraries.append({
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "available": info is not None,
                **(self._serialize_info(info) if info else {}),
            })
        return {"status": "success", "libraries": libraries}

    def discover(self) -> dict:
        return {
            "status": "success",
            "candidates": discover_paradox_localizations(GAME_PROFILES),
        }

    def _build_sync(
        self,
        game_id: str,
        localization_path: str,
        *,
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        profile = GAME_PROFILES_BY_ID.get(game_id)
        if profile is None:
            raise ValueError(f"Unsupported game: {game_id}")
        install_root = self._validate_profile_path(profile, localization_path)
        info = self.reference_service.build_index(
            game_id=game_id,
            localization_root=install_root,
            localization_globs=profile.get("official_localization_globs"),
            supported_language_keys=profile.get("supported_language_keys"),
            encoding=profile.get("encoding", "utf-8-sig"),
            progress_callback=progress_callback,
            allow_stale_fallback=False,
            force_rebuild=True,
        )
        return {
            "status": "success",
            "library": {
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "available": True,
                **self._serialize_info(info),
            },
        }

    def build(self, game_id: str, localization_path: str) -> dict:
        """Queue a single-game maintenance task and return its persisted state."""

        profile = GAME_PROFILES_BY_ID.get(game_id)
        if profile is None:
            raise ValueError(f"Unsupported game: {game_id}")
        return self._start_task(
            operation="build",
            candidates=[{
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "localization_path": localization_path,
            }],
        )

    def discover_and_build(self) -> dict:
        """Discover candidates and queue one task for all selected games."""

        candidates = discover_paradox_localizations(GAME_PROFILES)
        return self._start_task(operation="build", candidates=candidates)

    def start_operations(self, operations: list[dict]) -> dict:
        """Queue the explicitly selected build/update operations."""

        if not operations:
            raise ValueError("At least one reference library operation is required")
        candidates = []
        for operation in operations:
            game_id = str(operation.get("game_id", ""))
            profile = GAME_PROFILES_BY_ID.get(game_id)
            if profile is None:
                raise ValueError(f"Unsupported game: {game_id}")
            action = str(operation.get("action", "build"))
            if action not in {"build", "update"}:
                raise ValueError(f"Unsupported reference library action: {action}")
            candidates.append({
                "game_id": game_id,
                "game_name": profile.get("name", game_id),
                "localization_path": operation.get("localization_path", ""),
                "action": action,
            })
        return self._start_task(operation="build", candidates=candidates)

    def delete(self, game_id: str) -> dict:
        """Queue complete removal of one game's reference library."""

        if game_id not in GAME_PROFILES_BY_ID:
            raise ValueError(f"Unsupported game: {game_id}")
        active = self.reference_service.get_active_index(game_id)
        candidate = {
            "game_id": game_id,
            "game_name": GAME_PROFILES_BY_ID[game_id].get("name", game_id),
            "localization_path": active.root_path if active else "",
            "entries_total": self.reference_service.count_entries(active.reference_set_id) if active else 0,
        }
        return self._start_task(operation="delete", candidates=[candidate])

    def get_task(self, task_id: str) -> Optional[dict]:
        task = task_state.get_task_payload(task_id)
        if not task or task.get("kind") != REFERENCE_LIBRARY_TASK_KIND:
            return None
        return task

    def _start_task(self, *, operation: str, candidates: list[dict]) -> dict:
        existing = task_state.find_active_task_by_dedupe_key(REFERENCE_LIBRARY_DEDUPE_KEY)
        if existing is not None:
            return {"status": "accepted", "already_running": True, "task_id": existing["task_id"], "task": existing}

        task_id = f"reference-library-{uuid.uuid4().hex}"
        games = [self._initial_game_progress(item) for item in candidates]
        fields = {
            "kind": REFERENCE_LIBRARY_TASK_KIND,
            "title": "维护官方参考语料库",
            "blocking": True,
            "source_route": "/settings",
            "operation": operation,
            "candidates": candidates,
            "progress": self._overall_progress(games, stage="queued"),
        }
        try:
            task = task_state.create_task(
                task_id,
                status="queued",
                fields=fields,
                dedupe_key=REFERENCE_LIBRARY_DEDUPE_KEY,
                reject_duplicate=True,
                log_message="Official reference library maintenance queued.",
            )
        except task_state.DuplicateTaskError as exc:
            existing = exc.existing_task
            return {"status": "accepted", "already_running": True, "task_id": existing["task_id"], "task": existing}

        thread = threading.Thread(
            target=self._run_task,
            args=(task_id, operation, candidates),
            name="reference-library-maintenance",
            daemon=True,
        )
        thread.start()
        task = task_state.get_task_payload(task_id) or task
        return {"status": "accepted", "already_running": False, "task_id": task_id, "task": task}

    @staticmethod
    def _initial_game_progress(candidate: dict) -> dict:
        return {
            "game_id": candidate.get("game_id", ""),
            "game_name": candidate.get("game_name", candidate.get("game_id", "")),
            "localization_path": candidate.get("localization_path", ""),
            "stage": "queued",
            "status": "queued",
            "files_current": 0,
            "files_total": 0,
            "current_files": 0,
            "total_files": 0,
            "processed_files": 0,
            "entries_current": 0,
            "entries_total": candidate.get("entries_total"),
            "indexed_entries": 0,
            "error": None,
        }

    @staticmethod
    def _overall_progress(games: list[dict], *, stage: str) -> dict:
        completed = sum(item.get("status") in {"completed", "up_to_date"} for item in games)
        finished = sum(item.get("status") in {"completed", "up_to_date", "failed"} for item in games)
        total = len(games)
        percent = int(
            sum(
                100 if item.get("status") in {"completed", "up_to_date", "failed"}
                else int(item.get("percent") or 0)
                for item in games
            ) / total
        ) if total else 100
        return {
            "stage": stage,
            "current": finished,
            "total": total,
            "percent": percent,
            "completed_games": completed,
            "finished_games": finished,
            "total_games": total,
            "games": games,
        }

    def _run_task(self, task_id: str, operation: str, candidates: list[dict]) -> None:
        with _REFERENCE_WRITE_LOCK:
            self._run_task_locked(task_id, operation, candidates)

    def _run_task_locked(self, task_id: str, operation: str, candidates: list[dict]) -> None:
        games = [self._initial_game_progress(item) for item in candidates]
        task_state.update_task(task_id, status="running", message="Reference library maintenance started.", progress=self._overall_progress(games, stage="discovering"))
        results = []
        errors = []
        for index, candidate in enumerate(candidates):
            game = games[index]
            game["stage"] = "deleting" if operation == "delete" else "scanning"
            game["status"] = "running"
            self._publish_progress(task_id, games, stage=game["stage"])
            try:
                if operation == "delete":
                    result = self._delete_sync(candidate["game_id"], game)
                else:
                    result = self._build_sync(
                        candidate["game_id"],
                        candidate["localization_path"],
                        progress_callback=lambda update, current=game: self._update_index_progress(
                            task_id,
                            games,
                            current,
                            update,
                        ),
                    )
                    entry_count = int(result.get("library", {}).get("entry_count") or 0)
                    game["entries_current"] = entry_count
                    game["entries_total"] = entry_count
                    game["indexed_entries"] = entry_count
                game["stage"] = "completed"
                game["status"] = "completed"
                game["percent"] = 100
                results.append(result)
            except Exception as exc:
                game["stage"] = "failed"
                game["status"] = "failed"
                game["error"] = str(exc)
                errors.append({**candidate, "error": str(exc)})
            self._publish_progress(task_id, games, stage="running")

        final_status = "completed" if not errors else ("failed" if not results else "partial_failed")
        task_state.update_task(
            task_id,
            status=final_status,
            message=("Reference library maintenance completed." if not errors else "Reference library maintenance finished with errors."),
            progress=self._overall_progress(games, stage=final_status),
            fields={"result": {"operation": operation, "results": results, "errors": errors}},
            append_log=(None if not errors else f"{len(errors)} reference library operation(s) failed."),
        )

    def _publish_progress(self, task_id: str, games: list[dict], *, stage: str) -> None:
        task_state.update_task(task_id, progress=self._overall_progress(games, stage=stage), push=True)

    @staticmethod
    def _apply_index_progress(game: dict, update: dict) -> None:
        for key in ("stage", "current_file", "files_current", "files_total", "entries_current"):
            if key in update:
                game[key] = update[key]
        if "files_current" in update:
            game["current_files"] = update["files_current"]
            game["processed_files"] = update["files_current"]
        if "files_total" in update:
            game["total_files"] = update["files_total"]
        if "entries_current" in update:
            game["indexed_entries"] = update["entries_current"]
        if game.get("files_total"):
            game["percent"] = int((game["files_current"] / game["files_total"]) * 100)

    def _update_index_progress(
        self,
        task_id: str,
        games: list[dict],
        game: dict,
        update: dict,
    ) -> None:
        self._apply_index_progress(game, update)
        self._publish_progress(task_id, games, stage=str(update.get("stage") or "indexing"))

    def _delete_sync(self, game_id: str, game: dict) -> dict:
        game["entries_current"] = 0
        result = self.reference_service.delete_game_reference(game_id)
        game["entries_current"] = game.get("entries_total") or 0
        game["indexed_entries"] = game["entries_current"]
        if not result.get("database_compacted", False):
            raise OSError(
                "Reference data was deleted, but SQLite could not reclaim the freed disk space"
            )
        return {"game_id": game_id, **result}

    def _validate_profile_path(self, profile: dict, localization_path: str) -> Path:
        path = Path(localization_path).expanduser().resolve(strict=True)
        install_root = next(
            (
                candidate
                for candidate in (path, *path.parents)
                if candidate.parent.name.casefold() == "common"
                and candidate.parent.parent.name.casefold() == "steamapps"
            ),
            None,
        )
        if install_root is None:
            raise ValueError("Reference path must belong to a Steam game installation")
        official_roots = official_localization_roots(install_root, profile)
        if not official_roots:
            raise ValueError("No official localization directories were found for this game")
        if path != install_root and path not in official_roots:
            raise ValueError("Selected path is not an official localization directory for this game")
        return install_root

    def _serialize_info(self, info) -> dict:
        payload = asdict(info)
        payload["entry_count"] = self.reference_service.count_entries(info.reference_set_id)
        return payload
