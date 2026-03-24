import json
import os
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class ProjectJsonManager:
    """
    Manages the .remis_project.json sidecar file for project persistence.
    Stores Kanban state, configuration, and other metadata not suitable for SQLite.
    """

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.json_path = os.path.join(project_root, '.remis_project.json')
        self._ensure_json_exists()

    def _ensure_json_exists(self):
        """Creates the JSON file with default structure if it doesn't exist."""
        if not os.path.exists(self.json_path):
            default_data = {
                "version": "1.0",
                "config": {
                    "translation_dirs": [] # List of absolute paths
                },
                "kanban": {
                    "columns": ["todo", "in_progress", "proofreading", "paused", "done"],
                    "tasks": {}, # Map of taskId -> TaskObject
                    "column_order": ["todo", "in_progress", "proofreading", "paused", "done"]
                }
            }
            self._save_json(default_data)

    def _load_json(self) -> Dict[str, Any]:
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load project JSON: {e}")
            return {}

    def _save_json(self, data: Dict[str, Any]):
        try:
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save project JSON: {e}")

    def get_kanban_data(self) -> Dict[str, Any]:
        data = self._load_json()
        kanban = data.get("kanban", {})
        
        # Robustness: Auto-repair if columns are missing or corrupted (e.g. only 1 column)
        expected_columns = ["todo", "in_progress", "proofreading", "paused", "done"]
        columns = kanban.get("columns", [])
        
        if len(columns) < 3: # Heuristic: if fewer than 3 columns, something is wrong
            logger.warning(f"Kanban columns corrupted for {self.project_root}. Repairing...")
            kanban["columns"] = expected_columns
            kanban["column_order"] = expected_columns
            self.save_kanban_data(kanban)
            
        return kanban

    def save_kanban_data(self, kanban_data: Dict[str, Any]):
        data = self._load_json()
        data["kanban"] = kanban_data
        self._save_json(data)

    def get_config(self) -> Dict[str, Any]:
        data = self._load_json()
        return data.get("config", {})

    def update_config(self, config_updates: Dict[str, Any]):
        data = self._load_json()
        if "config" not in data:
            data["config"] = {}
        data["config"].update(config_updates)
        self._save_json(data)

    def add_translation_dir(self, dir_path: str):
        config = self.get_config()
        dirs = config.get("translation_dirs", [])
        if dir_path not in dirs:
            dirs.append(dir_path)
            self.update_config({"translation_dirs": dirs})

    def remove_translation_dir(self, dir_path: str):
        config = self.get_config()
        dirs = config.get("translation_dirs", [])
        if dir_path in dirs:
            dirs.remove(dir_path)
            self.update_config({"translation_dirs": dirs})

    def get_notes(self) -> List[Dict[str, Any]]:
        """Returns the list of notes, handles legacy string notes."""
        data = self._load_json()
        notes = data.get("notes", [])
        if isinstance(notes, str):
            # Legacy conversion
            if not notes: return []
            return [{
                "id": "legacy",
                "content": notes,
                "created_at": None
            }]
        return notes if isinstance(notes, list) else []

    def add_note(self, content: str):
        """Appends a new note with timestamp, ensures notes is a list."""
        import datetime
        data = self._load_json()
        
        notes = data.get("notes", [])
        if not isinstance(notes, list):
            # Convert legacy string or corrupted data to list
            if isinstance(notes, str) and notes:
                data["notes"] = [{
                    "id": "legacy",
                    "content": notes,
                    "created_at": None
                }]
            else:
                data["notes"] = []
        
        new_note = {
            "id": str(datetime.datetime.now().timestamp()),
            "content": content,
            "created_at": datetime.datetime.now().isoformat()
        }
        data["notes"].insert(0, new_note) # Prepend to show newest first
        self._save_json(data)

    def delete_note(self, note_id: str):
        """Deletes a note by ID."""
        data = self._load_json()
        if "notes" in data:
            data["notes"] = [note for note in data["notes"] if note["id"] != note_id]
            self._save_json(data)
