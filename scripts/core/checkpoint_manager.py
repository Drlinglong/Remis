"""Task-owned, atomic translation checkpoints."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set


class CheckpointManager:
    """Persist completed translation files and an explicit recovery contract."""

    CHECKPOINT_FILENAME = ".remis_checkpoint.json"
    SCHEMA_VERSION = 3
    SUPPORTED_SCHEMA_VERSIONS = {2, 3}
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
        self.batch_results: Dict[str, Dict[str, Dict[str, Any]]] = {}
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
        self.revision = 0
        self._batch_progress_base = 0
        self.read_enabled = True
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
            elif data.get("schema_version") in self.SUPPORTED_SCHEMA_VERSIONS:
                self._load_versioned(data)
            else:
                self._load_legacy(data)
        except (TypeError, ValueError) as exc:
            self.completed_files.clear()
            self.batch_results.clear()
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
        self.revision = max(1, int(data.get("revision") or 0))
        self.metadata = dict(data.get("metadata") or {})
        self.compatibility = "compatible"
        self._validate_legacy_config()

    def _load_versioned(self, data: Dict[str, Any]) -> None:
        self.revision = max(1, int(data.get("revision") or 0))
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
        batch_results = data.get("batch_results", {})
        if (
            not isinstance(completed, list)
            or not isinstance(progress, dict)
            or not isinstance(batch_results, dict)
        ):
            self.compatibility = "corrupt"
            self.compatibility_reason = "invalid_payload"
            return
        self.identity = dict(stored_identity)
        self.completed_files = {self._normalize_file_identity(item) for item in completed}
        self.batch_results = self._validate_batch_results(batch_results)
        self.progress = {
            key: int(progress.get(key) or 0)
            for key in ("completed_batches", "successful_batches", "failed_batches")
        }
        completed_batch_count = sum(len(items) for items in self.batch_results.values())
        self._batch_progress_base = max(
            0,
            self.progress["successful_batches"] - completed_batch_count,
        )
        self.metadata = dict(data.get("metadata") or self.current_config)
        self.compatibility = "compatible"

    def _validate_batch_results(
        self,
        batch_results: Dict[str, Any],
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        validated: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for filename, batches in batch_results.items():
            file_identity = self._normalize_file_identity(filename)
            if not isinstance(batches, dict):
                raise ValueError("Checkpoint batch collection must be an object")
            validated_batches: Dict[str, Dict[str, Any]] = {}
            for raw_index, raw_result in batches.items():
                batch_index = int(raw_index)
                canonical_index = str(batch_index)
                if (
                    batch_index < 0
                    or raw_index != canonical_index
                    or canonical_index in validated_batches
                    or not isinstance(raw_result, dict)
                ):
                    raise ValueError("Checkpoint batch result is invalid")
                start_index = int(raw_result.get("start_index"))
                end_index = int(raw_result.get("end_index"))
                source_hash = raw_result.get("source_hash")
                entry_indices = raw_result.get("source_entry_indices")
                translated_texts = raw_result.get("translated_texts")
                warnings = raw_result.get("warnings", [])
                if (
                    start_index < 0
                    or end_index < start_index
                    or raw_result.get("batch_index") != batch_index
                    or raw_result.get("status") != "succeeded"
                    or not isinstance(source_hash, str)
                    or not source_hash
                    or not isinstance(entry_indices, list)
                    or not all(isinstance(item, int) for item in entry_indices)
                    or not isinstance(translated_texts, list)
                    or not all(isinstance(item, str) for item in translated_texts)
                    or len(entry_indices) != len(translated_texts)
                    or end_index - start_index != len(translated_texts)
                    or not isinstance(warnings, list)
                    or not all(isinstance(item, dict) for item in warnings)
                ):
                    raise ValueError("Checkpoint batch payload is invalid")
                validated_batches[canonical_index] = {
                    "batch_index": batch_index,
                    "status": "succeeded",
                    "start_index": start_index,
                    "end_index": end_index,
                    "source_hash": source_hash,
                    "source_entry_indices": list(entry_indices),
                    "translated_texts": list(translated_texts),
                    "warnings": [dict(item) for item in warnings],
                    "completed_at": raw_result.get("completed_at"),
                }
            if validated_batches:
                validated[file_identity] = validated_batches
        return validated

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
            existing_revision = self._read_revision_from_disk()
            next_revision = max(self.revision, existing_revision) + 1
            metadata = dict(self.metadata or self.current_config)
            metadata["completed_count"] = len(self.completed_files)
            data = {
                "revision": next_revision,
                "metadata": metadata,
                "completed_files": sorted(self.completed_files),
                "batch_results": self.batch_results,
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
                os.replace(temp_path, self.checkpoint_path)
                self.revision = next_revision
                self.metadata = metadata
                self.compatibility = "compatible"
                self.compatibility_reason = None
            except (OSError, TypeError, ValueError) as exc:
                self.logger.error("Failed to save checkpoint: %s", exc)
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

    def is_file_completed(self, filename: str) -> bool:
        if not self.read_enabled or self.compatibility not in {"compatible", "missing"}:
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
            compacted_batches = self.batch_results.pop(normalized, {})
            self._batch_progress_base += len(compacted_batches)
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

    @staticmethod
    def _batch_source_hash(
        source_texts: List[str],
        source_entry_indices: List[int],
    ) -> str:
        encoded = json.dumps(
            {
                "source_texts": source_texts,
                "source_entry_indices": source_entry_indices,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def mark_batch_completed(
        self,
        filename: str,
        *,
        batch_index: int,
        start_index: int,
        end_index: int,
        source_texts: List[str],
        source_entry_indices: List[int],
        translated_texts: List[str],
        warnings: Optional[List[Dict[str, Any]]] = None,
        progress_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist one accepted batch result before the containing file completes."""
        if (
            batch_index < 0
            or start_index < 0
            or end_index < start_index
            or end_index - start_index != len(source_texts)
        ):
            raise ValueError("Checkpoint batch range is invalid")
        if len(source_texts) != len(translated_texts):
            raise ValueError("Checkpoint batch result length does not match its source")
        if len(source_entry_indices) != len(source_texts):
            raise ValueError("Checkpoint batch entry mapping does not match its source")
        if not all(isinstance(item, str) for item in source_texts + translated_texts):
            raise TypeError("Checkpoint batch text must be a string")
        safe_warnings = json.loads(json.dumps(warnings or [], ensure_ascii=False))
        if not all(isinstance(item, dict) for item in safe_warnings):
            raise TypeError("Checkpoint batch warnings must be objects")

        with self._lock:
            file_identity = self._normalize_file_identity(filename)
            batches = self.batch_results.setdefault(file_identity, {})
            batches[str(batch_index)] = {
                "batch_index": batch_index,
                "status": "succeeded",
                "start_index": start_index,
                "end_index": end_index,
                "source_hash": self._batch_source_hash(source_texts, source_entry_indices),
                "source_entry_indices": list(source_entry_indices),
                "translated_texts": list(translated_texts),
                "warnings": safe_warnings,
                "completed_at": datetime.now().isoformat(timespec="seconds"),
            }
            durable_count = self._batch_progress_base + sum(
                len(items) for items in self.batch_results.values()
            )
            self.progress = {
                "completed_batches": durable_count,
                "successful_batches": durable_count,
                "failed_batches": 0,
            }
            self.metadata = dict(self.metadata or self.current_config)
            self.metadata.update(progress_metadata or {})
            self.metadata.update(
                current_file=file_identity,
                last_completed_batch=batch_index,
                current_batch=durable_count,
                last_saved_at=datetime.now().isoformat(timespec="seconds"),
            )
        self.save_checkpoint()

    def restore_batch(
        self,
        filename: str,
        *,
        batch_index: int,
        start_index: int,
        end_index: int,
        source_texts: List[str],
        source_entry_indices: List[int],
    ) -> Optional[Dict[str, Any]]:
        """Return a batch only when its exact source partition still matches."""
        if not self.read_enabled or self.compatibility != "compatible":
            return None
        with self._lock:
            file_identity = self._normalize_file_identity(filename)
            result = self.batch_results.get(file_identity, {}).get(str(batch_index))
            if not result:
                return None
            expected_hash = self._batch_source_hash(source_texts, source_entry_indices)
            if (
                result["start_index"] != start_index
                or result["end_index"] != end_index
                or result["source_hash"] != expected_hash
                or result["source_entry_indices"] != source_entry_indices
                or len(result["translated_texts"]) != len(source_texts)
            ):
                return None
            return {
                "translated_texts": list(result["translated_texts"]),
                "warnings": [dict(item) for item in result["warnings"]],
            }

    def filter_pending_files(self, all_files_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.read_enabled or self.compatibility not in {"compatible", "missing"}:
            return list(all_files_data)
        with self._lock:
            completed = set(self.completed_files)
        return [
            item
            for item in all_files_data
            if self._normalize_file_identity(item.get("file_path") or item["filename"])
            not in completed
        ]

    def begin_fresh_run(self) -> None:
        """Ignore the saved slot in memory without deleting it from disk."""
        with self._lock:
            self.read_enabled = False
            self.completed_files.clear()
            self.batch_results.clear()
            self.metadata = dict(self.current_config)
            self.progress = {}
            self._batch_progress_base = 0
            self.compatibility = "missing"
            self.compatibility_reason = None

    def _read_revision_from_disk(self) -> int:
        if not os.path.exists(self.checkpoint_path):
            return 0
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as checkpoint_file:
                data = json.load(checkpoint_file)
            return max(1, int(data.get("revision") or 0)) if isinstance(data, dict) else 0
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return 0

    def clear_checkpoint(self) -> None:
        with self._lock:
            try:
                if os.path.exists(self.checkpoint_path):
                    os.remove(self.checkpoint_path)
            except OSError as exc:
                self.logger.warning("Failed to clear checkpoint file: %s", exc)
            self.completed_files.clear()
            self.batch_results.clear()
            self.metadata = dict(self.current_config)
            self.progress = {}
            self._batch_progress_base = 0
            self.compatibility = "missing"
            self.compatibility_reason = None
            self.revision = 0

    def get_checkpoint_info(self) -> Dict[str, Any]:
        with self._lock:
            completed_batch_count = sum(len(items) for items in self.batch_results.values())
            return {
                "exists": os.path.exists(self.checkpoint_path),
                "completed_count": len(self.completed_files),
                "completed_files": sorted(self.completed_files),
                "completed_batch_count": completed_batch_count,
                "completed_batches": {
                    filename: sorted(int(index) for index in batches)
                    for filename, batches in self.batch_results.items()
                },
                "metadata": dict(self.metadata),
                "last_saved_at": self.metadata.get("last_saved_at"),
                "last_completed_file": self.metadata.get("last_completed_file"),
                "identity": dict(self.identity),
                "revision": self.revision if os.path.exists(self.checkpoint_path) else 0,
                "progress": dict(self.progress),
                "compatibility": self.compatibility,
                "compatibility_reason": self.compatibility_reason,
                "resume_allowed": bool(
                    self.compatibility == "compatible"
                    and (self.completed_files or completed_batch_count)
                ),
            }
