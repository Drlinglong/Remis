import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from scripts.core.file_builder import rebuild_and_write_file

logger = logging.getLogger(__name__)


class IncrementalBuildService:
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

    def _build_dest_root(self, file_root: str, source_path: str, lang_output_dir: Path, target_lang_info: Dict[str, Any]) -> Path:
        rel_parts = list(Path(os.path.relpath(file_root, source_path)).parts)
        target_lang_folder = target_lang_info["key"][2:]

        for index, part in enumerate(rel_parts):
            if part.lower() in self.KNOWN_LANGUAGE_FOLDERS:
                rel_parts[index] = target_lang_folder
                return lang_output_dir / Path(*rel_parts)

        if "localization" in [part.lower() for part in rel_parts]:
            loc_index = next(
                index for index, part in enumerate(rel_parts)
                if part.lower() in {"localization", "localisation"}
            )
            rel_parts.insert(loc_index + 1, target_lang_folder)

        return lang_output_dir / Path(*rel_parts)

    def build_language_output(
        self,
        processing_records: List[Dict[str, Any]],
        translated_results: Dict[str, List[str]],
        source_path: str,
        lang_output_dir: Path,
        source_lang_info: Dict[str, Any],
        target_lang_info: Dict[str, Any],
        game_profile: Dict[str, Any],
    ) -> Dict[str, Any]:
        written_files: List[str] = []
        archive_files_data: List[Dict[str, Any]] = []
        archive_results: Dict[str, List[str]] = {}

        for record in processing_records:
            fd = record["fd"]
            filename = fd["filename"]
            full_entries = record["full_file_entries"]
            delta_indices = record["key_delta_indices"]

            ai_results = translated_results.get(filename, [])
            for delta_idx, trans_text in zip(delta_indices, ai_results):
                full_entries[delta_idx]["translation"] = trans_text

            all_texts = [entry["source"] for entry in full_entries]
            all_translations = [entry["translation"] or entry["source"] for entry in full_entries]

            rebuild_key_map = {
                index: {
                    "line_num": entry["line_num"],
                    "key_part": entry["key"],
                }
                for index, entry in enumerate(full_entries)
            }

            try:
                dest_root = self._build_dest_root(
                    file_root=fd["root"],
                    source_path=source_path,
                    lang_output_dir=lang_output_dir,
                    target_lang_info=target_lang_info,
                )
                os.makedirs(dest_root, exist_ok=True)

                out_path = rebuild_and_write_file(
                    original_lines=fd["original_lines"],
                    texts_to_translate=all_texts,
                    translated_texts=all_translations,
                    key_map=rebuild_key_map,
                    dest_dir=str(dest_root),
                    filename=filename,
                    source_lang=source_lang_info,
                    target_lang=target_lang_info,
                    game_profile=game_profile,
                )
                written_files.append(out_path)
            except Exception as e:
                logger.error(f"Failed to rebuild file {filename}: {e}")

            archive_files_data.append({
                "filename": filename,
                "file_path": fd["file_path"],
                "texts_to_translate": all_texts,
                "key_map": [{"key_part": entry["key"]} for entry in full_entries],
            })
            archive_results[fd["file_path"]] = all_translations

        return {
            "written_files": written_files,
            "archive_files_data": archive_files_data,
            "archive_results": archive_results,
        }
