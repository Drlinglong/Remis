"""Backend-authoritative recovery projection for translation tasks."""

from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from scripts.core.checkpoint_manager import CheckpointManager
from scripts.core.repositories.task_repository import TaskRepository
from scripts.core.services.translation_task_lifecycle import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    TRANSLATION_TASK_KINDS,
)


def canonical_configuration(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable, JSON-safe provider/workflow snapshot for one run."""
    excluded = {
        "idempotency_key",
        "resume_from_task_id",
        "use_resume",
        "expected_checkpoint_revision",
    }
    return {
        key: value
        for key, value in json.loads(json.dumps(payload, default=str)).items()
        if key not in excluded
    }


def configuration_fingerprint(configuration: dict[str, Any]) -> str:
    encoded = json.dumps(
        configuration,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_tree_hash(source_root: str) -> str:
    """Hash localization source bytes and stable relative paths without decoding text."""
    root = Path(source_root).resolve()
    if not root.is_dir():
        raise ValueError(f"Project source path not found: {source_root}")
    digest = hashlib.sha256()
    candidates = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".yml", ".yaml", ".txt"}
    )
    for path in candidates:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        with path.open("rb") as source_file:
            for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def build_recovery_descriptor(
    *,
    task_id: str,
    project_id: str,
    source_root: str,
    output_dir: str,
    target_lang_codes: Iterable[str],
    configuration: dict[str, Any],
    snapshot_hash: str,
    resumed_from_task_id: str | None = None,
    checkpoint_owner_task_id: str | None = None,
    checkpoint_owner_run_id: str | None = None,
) -> dict[str, Any]:
    run_id = task_id
    return {
        "schema_version": 1,
        "run_id": run_id,
        "project_id": project_id,
        "source_root": os.path.abspath(source_root),
        "output_dir": os.path.abspath(output_dir),
        "target_lang_codes": [str(code) for code in target_lang_codes],
        "configuration_snapshot": deepcopy(configuration),
        "config_fingerprint": configuration_fingerprint(configuration),
        "source_snapshot_hash": snapshot_hash,
        "resumed_from_task_id": resumed_from_task_id,
        "checkpoint_owner_task_id": checkpoint_owner_task_id or task_id,
        "checkpoint_owner_run_id": checkpoint_owner_run_id or run_id,
    }


class TranslationRecoveryService:
    """Resolve checkpoint actions from persisted task identity, never path heuristics."""

    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def latest_recovery_task(self, project_id: str) -> dict[str, Any] | None:
        """Return the latest persisted translation lifecycle for a project.

        A recovery projection must not resurrect an older failed/cancelled run
        after a newer run has completed (or is currently active).  Status is a
        projection concern; it cannot be used to select the authoritative run.
        """
        return self.repository.find_latest_project_task(
            project_id,
            kinds=TRANSLATION_TASK_KINDS,
        )

    def decorate_interrupted_task(self, task: dict[str, Any]) -> None:
        """Project authoritative checkpoint readiness onto one recovered task."""
        # Startup recovery decorates the task that was actually interrupted.
        # The project-level projection may already point at a newer lifecycle.
        projection = self._inspect_task(task)
        checkpoint = projection.get("checkpoint") or {}
        task["checkpoint"] = checkpoint
        task["attention_reason"] = (
            "The previous translation worker is no longer running. "
            "Resume from the saved checkpoint or start a new translation."
            if checkpoint.get("resumable") is True
            else "The previous translation worker is no longer running. Start a new translation."
        )
        task.setdefault("progress", {})["stage"] = "Interrupted"

    @staticmethod
    def _checkpoint_target_codes(
        recovery: dict[str, Any],
        *,
        include_unlisted: bool = False,
    ) -> list[str]:
        target_codes = {str(code) for code in recovery.get("target_lang_codes", [])}
        if target_codes and not include_unlisted:
            return sorted(target_codes)
        output_dir_value = recovery.get("output_dir")
        output_dir = Path(str(output_dir_value)) if output_dir_value else None
        if output_dir is not None and output_dir.is_dir():
            prefix = ".remis_checkpoint_"
            suffix = ".json"
            for checkpoint_path in output_dir.glob(f"{prefix}*{suffix}"):
                target_code = checkpoint_path.name[len(prefix):-len(suffix)]
                if target_code:
                    target_codes.add(target_code)
        return sorted(target_codes)

    @staticmethod
    def _checkpoint_managers(
        task: dict[str, Any],
        *,
        include_unlisted: bool = False,
    ) -> list[tuple[str, CheckpointManager]]:
        recovery = task.get("recovery") or {}
        return [
            (
                target_code,
                CheckpointManager(
                    recovery["output_dir"],
                    checkpoint_filename=f".remis_checkpoint_{target_code}.json",
                    source_root=recovery["source_root"],
                    task_id=recovery.get("checkpoint_owner_task_id") or str(task["task_id"]),
                    run_id=recovery.get("checkpoint_owner_run_id") or recovery["run_id"],
                    project_id=recovery["project_id"],
                    config_fingerprint=recovery["config_fingerprint"],
                    source_snapshot_hash=recovery["source_snapshot_hash"],
                ),
            )
            for target_code in TranslationRecoveryService._checkpoint_target_codes(
                recovery,
                include_unlisted=include_unlisted,
            )
        ]

    @staticmethod
    def _actions_for_task(task: dict[str, Any], *, resumable: bool, has_checkpoint: bool) -> list[str]:
        status = str(task.get("status") or "").lower()
        if status in {"completed", "complete", "success"}:
            actions = ["view_task", "archive_task"]
            if has_checkpoint:
                actions.insert(-1, "clear_checkpoint")
            return actions
        if status == "interrupted":
            actions = ["view_task"]
            if resumable:
                actions.append("resume_task")
            if has_checkpoint:
                actions.append("start_over_task")
                actions.append("clear_checkpoint")
            else:
                actions.append("return_to_workflow")
            actions.append("archive_task")
            return actions
        if status in {"failed", "cancelled"}:
            actions = ["view_task"]
            if resumable:
                actions.append("resume_task")
            if has_checkpoint:
                actions.append("clear_checkpoint")
            actions.extend(["return_to_workflow", "archive_task"])
            return actions
        if status in ACTIVE_STATUSES:
            return ["view_task"]
        if status in TERMINAL_STATUSES or status == "unknown":
            actions = ["view_task", "return_to_workflow", "archive_task"]
            if has_checkpoint:
                actions.insert(-1, "clear_checkpoint")
            return actions
        return ["view_task"]

    @staticmethod
    def _checkpoint_revision(target_infos: list[dict[str, Any]]) -> int:
        existing = [
            (str(item["target_lang_code"]), int(item.get("revision") or 0))
            for item in target_infos
            if item.get("exists")
        ]
        if not existing:
            return 0
        if len(existing) == 1:
            return existing[0][1]
        encoded = json.dumps(sorted(existing), separators=(",", ":")).encode("utf-8")
        return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")

    def _inspect_task(self, task: dict[str, Any]) -> dict[str, Any]:
        if not task.get("recovery"):
            return {
                "task_id": task["task_id"],
                "status": task.get("status") or "unknown",
                "progress": task.get("progress") or {},
                "checkpoint": {},
                "allowed_actions": self._actions_for_task(
                    task,
                    resumable=False,
                    has_checkpoint=False,
                ),
            }
        target_infos = [
            {"target_lang_code": code, **manager.get_checkpoint_info()}
            for code, manager in self._checkpoint_managers(task)
        ]
        existing = [item for item in target_infos if item["exists"]]
        incompatible = next(
            (item for item in existing if item["compatibility"] != "compatible"),
            None,
        )
        resumable = bool(existing) and incompatible is None and any(
            item["resume_allowed"] for item in existing
        )
        compatibility = (
            incompatible["compatibility"]
            if incompatible
            else ("compatible" if existing else "missing")
        )
        reason = incompatible.get("compatibility_reason") if incompatible else None
        return {
            "task_id": task["task_id"],
            "status": task["status"],
            "progress": task.get("progress") or {},
            "checkpoint": {
                "available": bool(existing),
                "resumable": resumable,
                "compatibility": compatibility,
                "reason_code": reason,
                "granularity": (
                    "batch"
                    if any(item.get("completed_batch_count", 0) for item in existing)
                    else "file"
                ),
                "completed_units": sum(item["completed_count"] for item in existing),
                "completed_batches": sum(
                    item.get("completed_batch_count", 0) for item in existing
                ),
                "revision": self._checkpoint_revision(target_infos),
                "targets": target_infos,
            },
            "allowed_actions": self._actions_for_task(
                task,
                resumable=resumable,
                has_checkpoint=bool(existing),
            ),
        }

    def inspect(self, project_id: str) -> dict[str, Any]:
        task = self.latest_recovery_task(project_id)
        if task is None:
            return {"task_id": None, "status": "none", "checkpoint": {}, "allowed_actions": []}
        return self._inspect_task(task)

    def require_resumable_identity(
        self,
        task_id: str,
        *,
        expected_checkpoint_revision: int | None = None,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise ValueError("Recovery task not found")
        project_id = str(task.get("project_id") or "")
        projection = self.inspect(project_id)
        if expected_checkpoint_revision is not None:
            actual_revision = (projection.get("checkpoint") or {}).get("revision", 0)
            if actual_revision != expected_checkpoint_revision:
                raise ValueError("The checkpoint revision changed; refresh recovery before resuming")
        if projection.get("task_id") != task_id or "resume_task" not in projection["allowed_actions"]:
            raise ValueError("Task does not have a compatible checkpoint")
        return task

    def require_resumable(
        self,
        task_id: str,
        *,
        expected_checkpoint_revision: int | None = None,
        source_snapshot_hash: str | None = None,
    ) -> dict[str, Any]:
        task = self.require_resumable_identity(
            task_id,
            expected_checkpoint_revision=expected_checkpoint_revision,
        )
        recovery = deepcopy(task.get("recovery") or {})
        current_hash = source_snapshot_hash or source_tree_hash(recovery["source_root"])
        if current_hash != recovery.get("source_snapshot_hash"):
            raise ValueError("Source snapshot changed; start over is required")
        return task

    def require_start_over(self, task_id: str) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise ValueError("Recovery task not found")
        if not task.get("recovery"):
            raise ValueError("Recovery task not found")
        project_id = str(task.get("project_id") or "")
        projection = self.inspect(project_id)
        if (
            str(task.get("status") or "").lower() != "interrupted"
            or projection.get("task_id") != task_id
            or "start_over_task" not in projection.get("allowed_actions", [])
        ):
            raise ValueError("Task does not allow start over")
        return task

    def clear_project_checkpoint(self, project_id: str) -> dict[str, Any]:
        """Explicitly clear the single recovery slot owned by one project."""
        task = self.latest_recovery_task(project_id)
        if task is None or not task.get("recovery"):
            return self.inspect(project_id)
        if str(task.get("status") or "").lower() in ACTIVE_STATUSES:
            raise ValueError("Cannot clear a checkpoint while translation is active")
        projection = self._inspect_task(task)
        if "clear_checkpoint" not in projection.get("allowed_actions", []):
            return projection
        for _target_code, manager in self._checkpoint_managers(
            task,
            include_unlisted=True,
        ):
            manager.clear_checkpoint()
        task["checkpoint"] = {
            "available": False,
            "resume_supported": bool(
                (task.get("checkpoint") or {}).get("resume_supported", True)
            ),
            "stage": "cleared",
            "metadata": {"cleared_by_user": True},
        }
        self.repository.save_task(task)
        return self.inspect(project_id)

    def finalize_start_over(
        self,
        task_id: str,
        *,
        replacement_task_id: str,
    ) -> dict[str, Any]:
        """Discard the old checkpoint only after its replacement owns the lock."""
        task = self.repository.get_task(task_id)
        replacement = self.repository.get_task(replacement_task_id)
        if task is None or not task.get("recovery"):
            raise ValueError("Recovery task not found")
        project_id = str(task.get("project_id") or "")
        lock = self.repository.get_project_lock(project_id)
        if (
            str(task.get("status") or "").lower() != "interrupted"
            or replacement is None
            or str(replacement.get("project_id") or "") != project_id
            or not lock
            or lock.get("task_id") != replacement_task_id
        ):
            raise ValueError("Replacement task does not own the project lock")
        for _target_code, manager in self._checkpoint_managers(
            task,
            include_unlisted=True,
        ):
            manager.clear_checkpoint()
        task["checkpoint"] = {
            "available": False,
            "resume_supported": False,
            "stage": "cleared",
            "metadata": {"cleared_by_action": True},
        }
        self.repository.save_task(task)
        return self.inspect(project_id)
