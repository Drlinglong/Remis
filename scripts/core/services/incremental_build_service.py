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
        from scripts.core.game_adapters.registry import resource_adapter
        structured = resource_adapter(game_profile)

        is_surviving_mars = game_profile.get("format_adapter_id") == "surviving_mars_csv"
        for record in processing_records:
            fd = record["fd"]
            filename = fd["filename"]
            full_entries = record["full_file_entries"]
            delta_indices = record["key_delta_indices"]
            canonical_entries = fd.get("canonical_entries", ())

            ai_results = translated_results.get(fd["file_path"] if structured else filename, [])
            if structured and len(ai_results) != len(delta_indices):
                raise ValueError(f"Incomplete incremental translations for {fd['file_path']}")
            for delta_idx, trans_text in zip(delta_indices, ai_results):
                full_entries[delta_idx]["translation"] = trans_text

            all_texts = [entry["source"] for entry in full_entries]
            all_translations = [entry["translation"] or entry["source"] for entry in full_entries]

            rebuild_key_map = {}
            for index, entry in enumerate(full_entries):
                rebuild_key_map[index] = {
                    "line_num": entry["line_num"],
                    "key_part": entry["key"],
                    "entry": entry.get("entry") or (
                        canonical_entries[index]
                        if index < len(canonical_entries)
                        else None
                    ),
                }
                if structured:
                    rebuild_key_map[index].update(fd.get("adapter_key_map", {}).get(index, {}))

            try:
                if structured and rebuild_key_map:
                    from dataclasses import replace
                    first = next(iter(rebuild_key_map.values()))
                    document = first["adapter_document"]
                    first["adapter_document"] = replace(document, metadata={**document.metadata,
                        "needs_review_keys": [e["key"] for e in full_entries if e.get("resolution") == "review"]})
                dest_root = (
                    lang_output_dir / Path(fd["file_path"]).parent
                    if is_surviving_mars
                    else self._build_dest_root(
                        file_root=fd["root"],
                        source_path=source_path,
                        lang_output_dir=lang_output_dir,
                        target_lang_info=target_lang_info,
                    )
                )
                if structured:
                    dest_root = lang_output_dir
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
                if structured:
                    raise

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
