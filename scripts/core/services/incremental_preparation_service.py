from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scripts.core.parallel_types import FileTask


class IncrementalPreparationService:
    def prepare_language_update(
        self,
        current_files_data: List[Dict[str, Any]],
        history_index: Dict[tuple[str, str], Dict[str, Any]],
        diff_service: Any,
        target_lang_info: Dict[str, Any],
        source_lang_info: Dict[str, Any],
        game_profile: Dict[str, Any],
        mod_context: str,
        selected_provider: str,
        source_path: str,
        base_output_dir: Path,
        total_targets: int,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
        file_tasks_for_ai: List[FileTask] = []
        processing_records: List[Dict[str, Any]] = []

        target_lang_code = target_lang_info["code"]
        lang_dest_dir = base_output_dir if total_targets == 1 else base_output_dir / target_lang_code
        num_files = len(current_files_data)

        for index, file_data in enumerate(current_files_data):
            filename = file_data["filename"]
            file_path = file_data["file_path"]

            if progress_callback:
                pct = 20 + int((index / num_files) * 30)
                progress_callback({
                    "stage": "Comparing",
                    "percent": pct,
                    "message": f"Comparing {filename} ({index + 1}/{num_files})",
                })

            texts_to_translate: List[str] = []
            key_delta_indices: List[int] = []
            full_file_entries: List[Dict[str, Any]] = []

            for key, source_text, line_num in file_data["parsed_entries"]:
                summary["total"] += 1
                status, history_entry = diff_service.classify_entry(file_path, key, source_text, history_index)

                entry_info = {
                    "key": key,
                    "source": source_text,
                    "line_num": line_num - 1,
                    "translation": None,
                    "is_dirty": False,
                }

                if status == "unchanged":
                    summary["unchanged"] += 1
                    entry_info["translation"] = history_entry["translation"] if history_entry else None
                else:
                    summary[status] += 1
                    entry_info["is_dirty"] = True
                    texts_to_translate.append(source_text)
                    key_delta_indices.append(len(full_file_entries))

                full_file_entries.append(entry_info)

            processing_records.append({
                "fd": file_data,
                "full_file_entries": full_file_entries,
                "key_delta_indices": key_delta_indices,
            })

            if texts_to_translate:
                file_tasks_for_ai.append(FileTask(
                    filename=filename,
                    root=file_data["root"],
                    original_lines=file_data["original_lines"],
                    texts_to_translate=texts_to_translate,
                    key_map={"indices": key_delta_indices},
                    is_custom_loc=False,
                    target_lang=target_lang_info,
                    source_lang=source_lang_info,
                    game_profile=game_profile,
                    mod_context=mod_context,
                    provider_name=selected_provider,
                    output_folder_name=f"IncrementalUpdate_{target_lang_code}",
                    source_dir=source_path,
                    dest_dir=str(lang_dest_dir),
                    client=None,
                    mod_name="",
                ))

        return {
            "summary": summary,
            "processing_records": processing_records,
            "file_tasks_for_ai": file_tasks_for_ai,
            "lang_output_dir": lang_dest_dir,
        }
