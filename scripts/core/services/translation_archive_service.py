import os
import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.archive_manager import archive_manager
from scripts.core.loc_parser import parse_loc_file
from scripts.schemas.common import LanguageCode

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


class TranslationArchiveService:
    """
    Builds a stable archive baseline for incremental update.
    This service is not a generic import tool. Its only responsibility is to
    create or refresh the source snapshot and attach any existing translations
    that can be matched back to that snapshot.
    """

    def __init__(self, am=None):
        self.archive_manager = am or archive_manager

    def upload_project_translations(
        self,
        project_id: str,
        project_name: str,
        source_path: str,
        source_lang_code: str = "en"
    ) -> Dict[str, Any]:
        try:
            json_manager = ProjectJsonManager(source_path)
            config = json_manager.get_config()
            translation_dirs = config.get("translation_dirs", [])
        except Exception as e:
            logger.error(f"Failed to load project config for {project_id}: {e}")
            return {"status": "error", "message": f"Failed to load project config: {e}"}

        try:
            paradox_source_lang = LanguageCode.from_str(source_lang_code).to_paradox()
        except ValueError:
            paradox_source_lang = "english"

        source_files_data = self._scan_source_files(source_path, paradox_source_lang)
        if not source_files_data:
            return {"status": "warning", "message": "No source files found to archive."}

        mod_id = self.archive_manager.get_or_create_mod_entry(project_name, project_id)
        if not mod_id:
            return {"status": "error", "message": "Failed to initialize mod archive entry."}

        version_id = self.archive_manager.create_source_version(mod_id, source_files_data)
        if not version_id:
            return {"status": "error", "message": "Failed to create source version snapshot."}

        if not translation_dirs:
            return {
                "status": "warning",
                "message": "Source snapshot archived, but no translation directories are configured.",
                "match_count": 0,
                "version_id": version_id,
            }

        file_results, match_count = self._scan_translation_dirs(
            source_files_data=source_files_data,
            source_path=source_path,
            translation_dirs=translation_dirs,
            paradox_source_lang=paradox_source_lang,
        )

        archived_languages = 0
        for lang_iso, results in file_results.items():
            if results:
                self.archive_manager.archive_translated_results(version_id, results, source_files_data, lang_iso)
                archived_languages += 1

        if match_count == 0:
            return {
                "status": "info",
                "message": "Source snapshot archived, but no matching translations were found.",
                "match_count": 0,
                "version_id": version_id,
            }

        return {
            "status": "success",
            "message": f"Archived source snapshot and imported {match_count} translations across {archived_languages} languages.",
            "match_count": match_count,
            "version_id": version_id,
        }

    def _scan_source_files(self, source_path: str, paradox_source_lang: str) -> List[Dict[str, Any]]:
        source_files_data: List[Dict[str, Any]] = []

        logger.info(f"Scanning source files in {source_path} (source language: {paradox_source_lang})")
        for root, dirs, files in os.walk(source_path):
            path_parts = [part.lower() for part in Path(root).parts]
            current_folder = os.path.basename(root).lower()
            if "localization" in path_parts or "localisation" in path_parts:
                # Only descend into the configured source language under localization trees.
                if current_folder in {"localization", "localisation"}:
                    dirs[:] = [
                        directory for directory in dirs
                        if directory.lower() not in KNOWN_LANGUAGE_FOLDERS
                        or directory.lower() == paradox_source_lang
                    ]
                if current_folder in KNOWN_LANGUAGE_FOLDERS and current_folder != paradox_source_lang:
                    continue

            for file_name in files:
                if not file_name.endswith((".yml", ".yaml")):
                    continue
                if not self._is_source_language_file(root, file_name, paradox_source_lang):
                    continue

                full_path = Path(os.path.join(root, file_name))
                try:
                    entries = parse_loc_file(full_path)
                except Exception as e:
                    logger.error(f"Failed to parse source file {full_path}: {e}")
                    continue

                if not entries:
                    continue

                relative_file_path = self._normalize_relpath(os.path.relpath(full_path, source_path))
                source_files_data.append({
                    "filename": os.path.basename(full_path),
                    "file_path": relative_file_path,
                    "key_map": [{"key_part": key} for key, _ in entries],
                    "texts_to_translate": [text for _, text in entries],
                })

        return source_files_data

    def _scan_translation_dirs(
        self,
        source_files_data: List[Dict[str, Any]],
        source_path: str,
        translation_dirs: List[str],
        paradox_source_lang: str,
    ) -> tuple[Dict[str, Dict[str, List[str]]], int]:
        source_by_relpath = {fd["file_path"]: fd for fd in source_files_data}
        source_candidates_by_key: Dict[str, List[Dict[str, Any]]] = {}

        for fd in source_files_data:
            for index, key_info in enumerate(fd["key_map"]):
                normalized_key = self._normalize_key(key_info["key_part"])
                source_candidates_by_key.setdefault(normalized_key, []).append({
                    "file_path": fd["file_path"],
                    "index": index,
                })

        file_results: Dict[str, Dict[str, List[str]]] = {}
        match_count = 0

        for trans_dir in translation_dirs:
            if not os.path.isdir(trans_dir):
                logger.warning(f"Translation directory not found: {trans_dir}")
                continue

            for root, _, files in os.walk(trans_dir):
                for file_name in files:
                    if not file_name.endswith((".yml", ".yaml", ".txt")):
                        continue

                    full_path = Path(os.path.join(root, file_name))
                    lang_iso = self._detect_translation_language(file_name, root)
                    if not lang_iso:
                        continue

                    try:
                        entries = parse_loc_file(full_path)
                    except Exception as e:
                        logger.error(f"Failed to parse translation file {full_path}: {e}")
                        continue

                    if not entries:
                        continue

                    relative_translation_path = self._normalize_relpath(os.path.relpath(full_path, trans_dir))
                    mapped_source_path = self._map_translation_path_to_source(
                        relative_translation_path,
                        paradox_source_lang,
                    )

                    source_file_data = source_by_relpath.get(mapped_source_path)
                    if source_file_data:
                        match_count += self._merge_translation_entries_for_file(
                            lang_iso,
                            source_file_data,
                            entries,
                            file_results,
                        )
                        continue

                    match_count += self._merge_translation_entries_by_unique_key(
                        lang_iso,
                        entries,
                        source_candidates_by_key,
                        source_by_relpath,
                        file_results,
                    )

        return file_results, match_count

    def _merge_translation_entries_for_file(
        self,
        lang_iso: str,
        source_file_data: Dict[str, Any],
        entries: List[tuple[str, str]],
        file_results: Dict[str, Dict[str, List[str]]],
    ) -> int:
        key_to_index = {
            self._normalize_key(key_info["key_part"]): index
            for index, key_info in enumerate(source_file_data["key_map"])
        }

        file_path = source_file_data["file_path"]
        results_for_language = file_results.setdefault(lang_iso, {})
        translations = results_for_language.setdefault(file_path, list(source_file_data["texts_to_translate"]))

        matched = 0
        for key, value in entries:
            index = key_to_index.get(self._normalize_key(key))
            if index is None:
                continue
            translations[index] = value
            matched += 1

        return matched

    def _merge_translation_entries_by_unique_key(
        self,
        lang_iso: str,
        entries: List[tuple[str, str]],
        source_candidates_by_key: Dict[str, List[Dict[str, Any]]],
        source_by_relpath: Dict[str, Dict[str, Any]],
        file_results: Dict[str, Dict[str, List[str]]],
    ) -> int:
        matched = 0
        for key, value in entries:
            candidates = source_candidates_by_key.get(self._normalize_key(key), [])
            if len(candidates) != 1:
                continue

            candidate = candidates[0]
            source_file_data = source_by_relpath[candidate["file_path"]]
            results_for_language = file_results.setdefault(lang_iso, {})
            translations = results_for_language.setdefault(
                candidate["file_path"],
                list(source_file_data["texts_to_translate"]),
            )
            translations[candidate["index"]] = value
            matched += 1

        return matched

    def _is_source_language_file(self, root: str, file_name: str, paradox_source_lang: str) -> bool:
        path_parts = [part.lower() for part in Path(root).parts]
        file_lower = file_name.lower()

        if "localization" in path_parts or "localisation" in path_parts:
            current_folder = os.path.basename(root).lower()
            if current_folder in KNOWN_LANGUAGE_FOLDERS and current_folder != paradox_source_lang:
                return False

        expected_suffixes = (
            f"l_{paradox_source_lang}.yml",
            f"l_{paradox_source_lang}.yaml",
            f" {paradox_source_lang}.yml",
            f" {paradox_source_lang}.yaml",
        )
        if file_lower.endswith(expected_suffixes):
            return True

        for language_folder in KNOWN_LANGUAGE_FOLDERS:
            if language_folder == paradox_source_lang:
                continue
            if f"l_{language_folder}" in file_lower or f" {language_folder}." in file_lower:
                return False

        return paradox_source_lang in path_parts

    def _detect_translation_language(self, file_name: str, root: str) -> Optional[str]:
        match = re.search(r"_l_([a-zA-Z0-9_-]+)\.(yml|yaml)$", file_name, re.IGNORECASE)
        if match:
            try:
                return LanguageCode.from_str(match.group(1)).value
            except ValueError:
                return None

        for part in reversed(Path(root).parts):
            lowered = part.lower()
            if lowered in KNOWN_LANGUAGE_FOLDERS:
                try:
                    return LanguageCode.from_str(lowered).value
                except ValueError:
                    return None

        return "zh-CN"

    def _map_translation_path_to_source(self, relative_translation_path: str, paradox_source_lang: str) -> str:
        path_obj = Path(relative_translation_path)
        parts = list(path_obj.parts)
        for index, part in enumerate(parts[:-1]):
            lowered = part.lower()
            if lowered in KNOWN_LANGUAGE_FOLDERS:
                parts[index] = paradox_source_lang
                break

        file_name = parts[-1]
        file_name = re.sub(
            r"_l_[a-zA-Z0-9_-]+(?=\.(yml|yaml)$)",
            f"_l_{paradox_source_lang}",
            file_name,
            flags=re.IGNORECASE,
        )
        parts[-1] = file_name
        return self._normalize_relpath(str(Path(*parts)))

    def _normalize_relpath(self, path: str) -> str:
        return path.replace("\\", "/")

    def _normalize_key(self, key: str) -> str:
        key = key.strip()
        if key.endswith(":"):
            key = key[:-1].strip()
        return key
