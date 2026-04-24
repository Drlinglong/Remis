import os
import json
import logging
import tempfile
import shutil
import threading
from datetime import datetime
from typing import List, Set, Dict, Any, Optional

class CheckpointManager:
    """
    Manages translation checkpoints to support resume functionality.
    Stores progress in a JSON file in the output directory.
    Thread-safe and metadata-aware.
    """

    CHECKPOINT_FILENAME = ".remis_checkpoint.json"

    def __init__(self, output_dir: str, current_config: Optional[Dict[str, Any]] = None, checkpoint_filename: str = ".remis_checkpoint.json"):
        self.output_dir = output_dir
        self.CHECKPOINT_FILENAME = checkpoint_filename
        self.checkpoint_path = os.path.join(output_dir, self.CHECKPOINT_FILENAME)
        self.completed_files: Set[str] = set()
        self.metadata: Dict[str, Any] = {}
        self.current_config = current_config or {}
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._load_checkpoint()

    def _load_checkpoint(self):
        """Loads existing checkpoint if available."""
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.completed_files = set(data.get("completed_files", []))
                    self.metadata = data.get("metadata", {})
                
                self.logger.info(f"Loaded checkpoint. {len(self.completed_files)} files already completed.")
                
                # Validate metadata if config is provided
                if self.current_config:
                    self._validate_config()
                    
            except Exception as e:
                self.logger.warning(f"Failed to load checkpoint: {e}. Starting fresh.")
                self.completed_files = set()
                self.metadata = {}
        else:
            self.completed_files = set()
            self.metadata = self.current_config

    def _validate_config(self):
        """Validates if the current config matches the checkpoint metadata."""
        # Keys to check for consistency
        critical_keys = ["model_name", "source_lang", "target_lang_code"]
        
        mismatches = []
        for key in critical_keys:
            stored_val = self.metadata.get(key)
            current_val = self.current_config.get(key)
            
            # Allow minor differences or if key is missing in one (backward compatibility)
            # But for strict safety, we warn.
            if stored_val and current_val and stored_val != current_val:
                mismatches.append(f"{key}: stored='{stored_val}', current='{current_val}'")
        
        if mismatches:
            self.logger.warning(f"Checkpoint configuration mismatch: {', '.join(mismatches)}")
            # TODO: Decide whether to invalidate checkpoint or just warn.
            # For now, we warn but allow resume (user might want to switch models mid-way intentionally?)
            # The user requirement says: "Must warn user or via UI prompt".
            # Since this class is backend logic, we just log warning here. 
            # The UI check endpoint should handle the user prompt.
            pass

    def save_checkpoint(self):
        """Saves current progress to checkpoint file atomically."""
        with self._lock:
            metadata = dict(self.metadata if self.metadata else self.current_config)
            metadata["completed_count"] = len(self.completed_files)
            data = {
                "metadata": metadata,
                "completed_files": list(self.completed_files)
            }
            
            try:
                # Write to temp file first then rename to ensure atomicity
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', dir=self.output_dir) as tmp:
                    json.dump(data, tmp, ensure_ascii=False, indent=2)
                    tmp_path = tmp.name
                
                shutil.move(tmp_path, self.checkpoint_path)
            except Exception as e:
                self.logger.error(f"Failed to save checkpoint: {e}")

    def is_file_completed(self, filename: str) -> bool:
        """Checks if a file has been successfully processed."""
        with self._lock:
            return filename in self.completed_files

    def mark_file_completed(self, filename: str, progress_metadata: Optional[Dict[str, Any]] = None):
        """Marks a file as completed and saves checkpoint."""
        with self._lock:
            self.completed_files.add(filename)
            self.metadata = dict(self.metadata if self.metadata else self.current_config)
            self.metadata["last_completed_file"] = filename
            self.metadata["last_saved_at"] = datetime.now().isoformat(timespec="seconds")
            self.metadata["completed_count"] = len(self.completed_files)
            if progress_metadata:
                self.metadata.update(progress_metadata)

            recent_files = list(self.metadata.get("recent_completed_files", []))
            recent_files.append(filename)
            self.metadata["recent_completed_files"] = recent_files[-10:]
        # Save outside the lock to minimize blocking time? 
        # No, save_checkpoint uses lock too. 
        # Actually, we should save inside lock or make save_checkpoint re-entrant safe?
        # save_checkpoint acquires lock. So we shouldn't hold lock when calling it if it's not re-entrant.
        # RLock would solve this, or just calling save_checkpoint (which locks) is enough.
        # But we need to add to set atomically.
        
        # Correct pattern:
        # with self._lock:
        #    self.completed_files.add(filename)
        # self.save_checkpoint() 
        
        # But if another thread adds between add and save, it's fine.
        self.save_checkpoint()

    def filter_pending_files(self, all_files_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Returns a list of files that still need to be processed."""
        with self._lock:
            completed_snapshot = self.completed_files.copy()
            
        pending = []
        for fd in all_files_data:
            if fd["filename"] not in completed_snapshot:
                pending.append(fd)
        
        skipped_count = len(all_files_data) - len(pending)
        if skipped_count > 0:
            self.logger.info(f"Skipping {skipped_count} already completed files based on checkpoint.")
        
        return pending

    def clear_checkpoint(self):
        """Deletes the checkpoint file upon successful completion."""
        with self._lock:
            if os.path.exists(self.checkpoint_path):
                try:
                    os.remove(self.checkpoint_path)
                    self.logger.info("Checkpoint file cleared.")
                except Exception as e:
                    self.logger.warning(f"Failed to clear checkpoint file: {e}")

    def get_checkpoint_info(self) -> Dict[str, Any]:
        """Returns info about the checkpoint for UI display."""
        with self._lock:
            return {
                "exists": os.path.exists(self.checkpoint_path),
                "completed_count": len(self.completed_files),
                "metadata": self.metadata,
                "last_saved_at": self.metadata.get("last_saved_at"),
                "last_completed_file": self.metadata.get("last_completed_file"),
            }
