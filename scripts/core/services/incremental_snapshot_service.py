import os
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scripts.core.loc_parser import parse_loc_file_with_lines
from scripts.utils import read_text_bom

logger = logging.getLogger(__name__)

KNOWN_LANGUAGE_FOLDERS = {
    "english",
    "french",
    "german",
    "spanish",
    "russian",
    "polish",
    "braz_por",
    "japanese",
    "chinese",
    "simp_chinese",
    "trad_chinese",
    "korean",
    "turkish",
}


class IncrementalSnapshotService:
    def build_snapshot(
        self,
        source_path: str,
        source_lang_info: Dict[str, Any],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        filter_lang_string = self._resolve_source_lang_folder(source_lang_info)
        files_data: List[Dict[str, Any]] = []

        for root, dirs, files in os.walk(source_path):
            path_parts = [part.lower() for part in Path(root).parts]
            if "localization" in path_parts or "localisation" in path_parts:
                current_folder = os.path.basename(root).lower()
                if current_folder in {"localization", "localisation"}:
                    dirs[:] = [
                        directory for directory in dirs
                        if directory.lower() not in KNOWN_LANGUAGE_FOLDERS
                        or directory.lower() == filter_lang_string
                    ]
                if current_folder in KNOWN_LANGUAGE_FOLDERS and current_folder != filter_lang_string:
                    dirs[:] = []
                    continue

            for file_name in files:
                if not file_name.endswith((".yml", ".yaml")):
                    continue
                if not self._matches_source_language(file_name, filter_lang_string):
                    continue

                full_path = Path(os.path.join(root, file_name))
                try:
                    parsed_entries = parse_loc_file_with_lines(full_path)
                    if not parsed_entries:
                        continue

                    raw_content = read_text_bom(full_path)
                    original_lines = raw_content.splitlines(keepends=True)
                    relative_file_path = os.path.relpath(full_path, source_path).replace("\\", "/")

                    files_data.append({
                        "filename": os.path.basename(full_path),
                        "file_path": relative_file_path,
                        "full_path": full_path,
                        "root": root,
                        "original_lines": original_lines,
                        "parsed_entries": parsed_entries,
                    })
                except Exception as e:
                    logger.error(f"Failed to parse {full_path}: {e}")

            if progress_callback:
                progress_callback({
                    "stage": "Scanning",
                    "percent": 10,
                    "message": f"Scanned {len(files_data)} files.",
                })

        return files_data

    def _resolve_source_lang_folder(self, source_lang_info: Dict[str, Any]) -> str:
        source_lang_name_en = source_lang_info.get("name_en", "English").lower()
        paradox_lang_map = {
            "simplified chinese": "simp_chinese",
            "traditional chinese": "trad_chinese",
            "brazilian portuguese": "braz_por",
        }
        return paradox_lang_map.get(source_lang_name_en, source_lang_name_en)

    def _matches_source_language(self, file_name: str, filter_lang_string: str) -> bool:
        file_lower = file_name.lower()
        expected_suffixes = (
            f"l_{filter_lang_string}.yml",
            f"l_{filter_lang_string}.yaml",
            f" {filter_lang_string}.yml",
            f" {filter_lang_string}.yaml",
        )
        if file_lower.endswith(expected_suffixes):
            return True

        for lang in KNOWN_LANGUAGE_FOLDERS:
            if lang == filter_lang_string:
                continue
            if f"l_{lang}" in file_lower or f" {lang}." in file_lower:
                return False

        return True
