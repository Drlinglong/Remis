from typing import Any, Dict, List, Optional

from scripts.core.archive_manager import archive_manager
from scripts.core.archive_result_persistence import ArchivePersistenceError


class IncrementalArchiveService:
    def __init__(self, am=None):
        self.archive_manager = am or archive_manager

    def get_language_entries(self, project_id: str, language_code: str) -> List[Dict[str, Any]]:
        entries = self.archive_manager.get_entries(project_id=project_id, language=language_code)
        if language_code == "custom" and not any((entry.get("translation") or "").strip() for entry in entries):
            raise ValueError("Shell incremental updates require an existing custom-language baseline")
        return entries

    def get_language_baseline(self, project_id: str, language_code: str) -> Optional[Dict[str, Any]]:
        return self.archive_manager.get_latest_version(project_id=project_id, language=language_code)

    def archive_language_result(
        self,
        project_id: str,
        project_name: str,
        target_lang_code: str,
        archive_files_data: List[Dict[str, Any]],
        archive_results: Dict[str, List[str]],
    ) -> Optional[int]:
        mod_id = self.archive_manager.resolve_mod_entry(project_name, remote_file_id=project_id)
        if not mod_id:
            return None

        version_id = self.archive_manager.create_source_version(mod_id, archive_files_data)
        if not version_id:
            return None

        self.archive_manager.archive_translated_results(
            version_id,
            archive_results,
            archive_files_data,
            target_lang_code,
        )
        return version_id

    def archive_built_output(self, project_id, project_name, language_code, build_result, warnings):
        try:
            version = self.archive_language_result(
                project_id=project_id,
                project_name=project_name,
                target_lang_code=language_code,
                archive_files_data=build_result["archive_files_data"],
                archive_results=build_result["archive_results"],
            )
        except ArchivePersistenceError:
            if language_code != "custom":
                raise
            version = None
        if language_code == "custom" and version is None:
            warnings.append({
                "code": "incremental_archive_write_failed",
                "target_lang": language_code,
                "message": "Saved shell output, but could not update its archive baseline.",
            })
        return version
