import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from scripts.utils.validation_issue_identity import enrich_issues

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
    def _matches_issue(err: Dict[str, Any], file_name: str, key: str, issue_id: Optional[str]) -> bool:
        if issue_id:
            return bool(err.get("issue_id")) and err.get("issue_id") == issue_id
        return err.get("file_name") == file_name and err.get("key") == key

    @staticmethod
    def update_error_status(
        project_root: str,
        file_name: str,
        key: str,
        status: str,
        issue_id: Optional[str] = None,
    ):
        """
        Updates the status of a specific error entry.
        """
        errors = ValidationLogger.load_errors(project_root)
        updated = False
        for err in errors:
            if ValidationLogger._matches_issue(err, file_name, key, issue_id):
                err['status'] = status
                updated = True
                if issue_id:
                    break
        
        if updated:
            ValidationLogger.save_errors(project_root, errors)

    @staticmethod
    def update_error_metadata(
        project_root: str,
        file_name: str,
        key: str,
        updates: Dict[str, Any],
        issue_id: Optional[str] = None,
    ):
        """
        Updates arbitrary metadata for a specific error entry.
        """
        errors = ValidationLogger.load_errors(project_root)
        updated = False
        for err in errors:
            if ValidationLogger._matches_issue(err, file_name, key, issue_id):
                err.update(updates)
                updated = True
                if issue_id:
                    break

        if updated:
            ValidationLogger.save_errors(project_root, errors)

    @staticmethod
    def ensure_issue_identity(project_root: str, issue: Dict[str, Any]) -> bool:
        """Migrate one unbound legacy entry before strict ID-based updates."""
        errors = ValidationLogger.load_errors(project_root)
        enriched = enrich_issues(errors)
        matches = [
            index for index, candidate in enumerate(enriched)
            if candidate.get("file_name") == issue.get("file_name")
            and candidate.get("key") == issue.get("key")
            and candidate.get("source_hash") == issue.get("source_hash")
            and candidate.get("target_hash") == issue.get("target_hash")
            and (
                not issue.get("error_code")
                or not candidate.get("error_code")
                or candidate.get("error_code") == issue.get("error_code")
            )
        ]
        if len(matches) != 1 or not issue.get("issue_id"):
            return False
        index = matches[0]
        errors[index].update({
            "issue_id": issue["issue_id"],
            "observation_fingerprint": issue.get("observation_fingerprint"),
            "source_hash": issue.get("source_hash"),
            "target_hash": issue.get("target_hash"),
            "classification": issue.get("classification"),
            "repairable": issue.get("repairable"),
            "repair_queue": issue.get("repair_queue"),
            "review_queue": issue.get("review_queue"),
            "disposition": issue.get("disposition"),
        })
        ValidationLogger.save_errors(project_root, errors)
        return True

    @staticmethod
    def mark_attempt_result(
        project_root: str,
        file_name: str,
        key: str,
        *,
        status: str,
        issue_id: Optional[str] = None,
        disposition: Optional[str] = None,
        failure_reason: Optional[str] = None,
        failure_details: Optional[str] = None,
        last_suggested_fix: Optional[str] = None,
    ):
        """
        Records the latest attempt outcome for a specific issue.
        """
        payload: Dict[str, Any] = {
            "status": status,
            "last_attempt_at": datetime.now().isoformat(timespec="seconds"),
        }
        if disposition is not None:
            payload["disposition"] = disposition
        elif status == "fixed":
            payload["disposition"] = "fixed"
        elif status == "review":
            payload["disposition"] = "human_review"
        if last_suggested_fix is not None:
            payload["last_suggested_fix"] = last_suggested_fix

        if status == "failed":
            payload["failure_reason"] = failure_reason or "unknown_failure"
            payload["failure_details"] = failure_details or ""
        else:
            payload["failure_reason"] = None
            payload["failure_details"] = None

        errors = ValidationLogger.load_errors(project_root)
        candidate_indices = [
            index for index, err in enumerate(errors)
            if ValidationLogger._matches_issue(err, file_name, key, issue_id)
        ]
        if len(candidate_indices) == 1:
            err = errors[candidate_indices[0]]
            err.update(payload)
            err["attempts"] = int(err.get("attempts") or 0) + 1
            updated = True
        else:
            updated = False
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
