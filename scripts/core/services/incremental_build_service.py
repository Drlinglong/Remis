import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from scripts.core.file_builder import rebuild_and_write_file

logger = logging.getLogger(__name__)


class IncrementalBuildService:
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
                rel_path = os.path.relpath(fd["root"], source_path)
                dest_root = lang_output_dir / rel_path
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
