"""Task-owned, atomic translation checkpoints."""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set


class CheckpointManager:
    """Persist completed translation files and an explicit recovery contract."""

    CHECKPOINT_FILENAME = ".remis_checkpoint.json"
    SCHEMA_VERSION = 2

    def __init__(
        self,
        output_dir: str,
        current_config: Optional[Dict[str, Any]] = None,
        checkpoint_filename: str = CHECKPOINT_FILENAME,
        *,
        source_root: Optional[str] = None,
        task_id: Optional[str] = None,
        run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        config_fingerprint: Optional[str] = None,
        source_snapshot_hash: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.CHECKPOINT_FILENAME = checkpoint_filename
        self.checkpoint_path = os.path.join(output_dir, checkpoint_filename)
        self.source_root = Path(source_root).resolve() if source_root else None
        self.completed_files: Set[str] = set()
        self.current_config = dict(current_config or {})
        self.identity = {
            key: value
            for key, value in {
                "task_id": task_id,
                "run_id": run_id,
                "project_id": project_id,
                "config_fingerprint": config_fingerprint,
                "source_snapshot_hash": source_snapshot_hash,
            }.items()
            if value is not None
        }
        self.metadata: Dict[str, Any] = dict(self.current_config)
        self.progress: Dict[str, int] = {}
        self.compatibility = "missing"
        self.compatibility_reason: Optional[str] = None
        self.logger = logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._load_checkpoint()

    @property
    def uses_v2_contract(self) -> bool:
        return bool(self.identity)

    def _load_checkpoint(self) -> None:
        if not os.path.exists(self.checkpoint_path):
            return
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as checkpoint_file:
                data = json.load(checkpoint_file)
        except json.JSONDecodeError as exc:
            self.compatibility = "corrupt"
            self.compatibility_reason = "corrupt_json"
            self.logger.warning("Checkpoint JSON is corrupt: %s", exc)
            return
        except (OSError, TypeError) as exc:
            self.compatibility = "corrupt"
            self.compatibility_reason = "checkpoint_read_failed"
            self.logger.warning("Checkpoint could not be read: %s", exc)
            return
        try:
            if not isinstance(data, dict):
                self.compatibility = "corrupt"
                self.compatibility_reason = "invalid_payload"
            elif data.get("schema_version") == self.SCHEMA_VERSION:
                self._load_v2(data)
            else:
                self._load_legacy(data)
        except (TypeError, ValueError) as exc:
            self.completed_files.clear()
            self.compatibility = "corrupt"
            self.compatibility_reason = "invalid_file_identity"
            self.logger.warning("Checkpoint contains an invalid file identity: %s", exc)

    def _load_legacy(self, data: Dict[str, Any]) -> None:
        if self.uses_v2_contract:
            self.compatibility = "incompatible"
            self.compatibility_reason = "legacy_format"
            return
        self.completed_files = {
            self._normalize_file_identity(item) for item in data.get("completed_files", [])
        }
        self.metadata = dict(data.get("metadata") or {})
        self.compatibility = "compatible"
        self._validate_legacy_config()

    def _load_v2(self, data: Dict[str, Any]) -> None:
        stored_identity = data.get("identity")
        if not isinstance(stored_identity, dict):
            self.compatibility = "corrupt"
            self.compatibility_reason = "missing_identity"
            return
        for key, reason in (
            ("task_id", "task_mismatch"),
            ("run_id", "run_mismatch"),
            ("project_id", "project_mismatch"),
            ("config_fingerprint", "config_mismatch"),
            ("source_snapshot_hash", "source_snapshot_mismatch"),
        ):
            expected = self.identity.get(key)
            if expected is not None and stored_identity.get(key) != expected:
                self.compatibility = "incompatible"
                self.compatibility_reason = reason
                return
        completed = data.get("completed_files", [])
        progress = data.get("progress", {})
        if not isinstance(completed, list) or not isinstance(progress, dict):
            self.compatibility = "corrupt"
            self.compatibility_reason = "invalid_payload"
            return
        self.identity = dict(stored_identity)
        self.completed_files = {self._normalize_file_identity(item) for item in completed}
        self.progress = {
            key: int(progress.get(key) or 0)
            for key in ("completed_batches", "successful_batches", "failed_batches")
        }
        self.metadata = dict(data.get("metadata") or self.current_config)
        self.compatibility = "compatible"

    def _validate_legacy_config(self) -> None:
        mismatches = []
        for key in ("model_name", "source_lang", "target_lang_code"):
            stored = self.metadata.get(key)
            current = self.current_config.get(key)
            if stored and current and stored != current:
                mismatches.append(key)
        if mismatches:
            self.logger.warning(
                "Legacy checkpoint configuration mismatch: %s", ", ".join(mismatches)
            )

    def _normalize_file_identity(self, filename: Any) -> str:
        value = str(filename or "").replace("\\", "/")
        raw_identity = PurePosixPath(value)
        if ".." in raw_identity.parts:
            raise ValueError("Checkpoint file identity must not contain parent traversal")
        candidate = Path(value)
        if candidate.is_absolute():
            if not self.source_root:
                raise ValueError("Absolute checkpoint file identity requires a source root")
            try:
                value = candidate.resolve().relative_to(self.source_root).as_posix()
            except ValueError as exc:
                raise ValueError("Checkpoint file is outside the configured source root") from exc
        normalized_identity = PurePosixPath(value)
        normalized = normalized_identity.as_posix()
        if (
            not normalized
            or normalized == "."
            or normalized_identity.is_absolute()
            or ".." in normalized_identity.parts
        ):
            raise ValueError("Checkpoint file identity must stay inside the source root")
        return normalized

    def save_checkpoint(self) -> None:
        with self._lock:
            os.makedirs(self.output_dir, exist_ok=True)
            metadata = dict(self.metadata or self.current_config)
            metadata["completed_count"] = len(self.completed_files)
            data = {
                "metadata": metadata,
                "completed_files": sorted(self.completed_files),
            }
            if self.uses_v2_contract:
                data.update(
                    schema_version=self.SCHEMA_VERSION,
                    identity=dict(self.identity),
                    progress=dict(self.progress),
                )
            temp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", delete=False, encoding="utf-8", dir=self.output_dir
                ) as temp_file:
                    json.dump(data, temp_file, ensure_ascii=False, indent=2)
                    temp_path = temp_file.name
                shutil.move(temp_path, self.checkpoint_path)
                self.metadata = metadata
                self.compatibility = "compatible"
                self.compatibility_reason = None
            except OSError as exc:
                self.logger.error("Failed to save checkpoint: %s", exc)
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

    def is_file_completed(self, filename: str) -> bool:
        if self.compatibility not in {"compatible", "missing"}:
            return False
        with self._lock:
            return self._normalize_file_identity(filename) in self.completed_files

    def mark_file_completed(
        self,
        filename: str,
        progress_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            normalized = self._normalize_file_identity(filename)
            self.completed_files.add(normalized)
            self.metadata = dict(self.metadata or self.current_config)
            self.metadata["last_completed_file"] = normalized
            self.metadata["last_saved_at"] = datetime.now().isoformat(timespec="seconds")
            if progress_metadata:
                for key in ("completed_batches", "successful_batches", "failed_batches"):
                    if key in progress_metadata:
                        self.progress[key] = int(progress_metadata[key])
                self.metadata.update(progress_metadata)
            recent = list(self.metadata.get("recent_completed_files", []))
            recent.append(normalized)
            self.metadata["recent_completed_files"] = recent[-10:]
        self.save_checkpoint()

    def filter_pending_files(self, all_files_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.compatibility not in {"compatible", "missing"}:
            return list(all_files_data)
        with self._lock:
            completed = set(self.completed_files)
        return [
            item
            for item in all_files_data
            if self._normalize_file_identity(item.get("file_path") or item["filename"])
            not in completed
        ]

    def clear_checkpoint(self) -> None:
        with self._lock:
            try:
                if os.path.exists(self.checkpoint_path):
                    os.remove(self.checkpoint_path)
            except OSError as exc:
                self.logger.warning("Failed to clear checkpoint file: %s", exc)
            self.completed_files.clear()
            self.metadata = dict(self.current_config)
            self.progress = {}
            self.compatibility = "missing"
            self.compatibility_reason = None

    def get_checkpoint_info(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "exists": os.path.exists(self.checkpoint_path),
                "completed_count": len(self.completed_files),
                "completed_files": sorted(self.completed_files),
                "metadata": dict(self.metadata),
                "last_saved_at": self.metadata.get("last_saved_at"),
                "last_completed_file": self.metadata.get("last_completed_file"),
                "identity": dict(self.identity),
                "progress": dict(self.progress),
                "compatibility": self.compatibility,
                "compatibility_reason": self.compatibility_reason,
                "resume_allowed": bool(
                    self.compatibility == "compatible" and self.completed_files
                ),
            }
