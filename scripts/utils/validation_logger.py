import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

class ValidationLogger:
    """
    Manages the .remis_errors.json sidecar file in project roots.
    """
    
    FILENAME = ".remis_errors.json"
    
    @staticmethod
    def _get_log_path(project_root: str) -> Path:
        return Path(project_root) / ValidationLogger.FILENAME
    
    @staticmethod
    def load_errors(project_root: str) -> List[Dict[str, Any]]:
        """
        Loads errors from the .remis_errors.json file.
        """
        log_path = ValidationLogger._get_log_path(project_root)
        if not log_path.exists():
            return []
            
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Failed to load validation log at {log_path}: {e}")
            return []
            
    @staticmethod
    def save_errors(project_root: str, errors: List[Dict[str, Any]]):
        """
        Saves the list of errors to the .remis_errors.json file.
        """
        log_path = ValidationLogger._get_log_path(project_root)
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(errors, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save validation log at {log_path}: {e}")

    @staticmethod
    def update_error_status(project_root: str, file_name: str, key: str, status: str):
        """
        Updates the status of a specific error entry.
        """
        errors = ValidationLogger.load_errors(project_root)
        updated = False
        for err in errors:
            if err.get('file_name') == file_name and err.get('key') == key:
                err['status'] = status
                updated = True
        
        if updated:
            ValidationLogger.save_errors(project_root, errors)

    @staticmethod
    def clear_fixes(project_root: str):
        """
        Removes all errors marked as 'fixed' or 'ignored'.
        """
        errors = ValidationLogger.load_errors(project_root)
        filtered = [err for err in errors if err.get('status') not in ('fixed', 'ignored')]
        ValidationLogger.save_errors(project_root, filtered)
