from typing import Any, Dict, List, Optional

from scripts.core.archive_manager import archive_manager


class IncrementalArchiveService:
    def __init__(self, am=None):
        self.archive_manager = am or archive_manager

    def get_language_entries(self, project_id: str, language_code: str) -> List[Dict[str, Any]]:
        return self.archive_manager.get_entries(project_id=project_id, language=language_code)

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
        mod_id = self.archive_manager.get_or_create_mod_entry(project_name, remote_file_id=project_id)
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
