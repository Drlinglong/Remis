from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scripts.core.parallel_types import FileTask


def _prepare_file_entries(
    file_data: Dict[str, Any],
    history_index: Dict[tuple[str, str], Dict[str, Any]],
    diff_service: Any,
    target_lang_code: str,
    summary: Dict[str, int],
    file_summary: Dict[str, Any],
    reference_resolver: Optional[Any],
    reference_protected_entries: List[Dict[str, str]],
) -> tuple[List[str], List[int], List[Dict[str, Any]]]:
    texts_to_translate: List[str] = []
    key_delta_indices: List[int] = []
    full_file_entries: List[Dict[str, Any]] = []
    canonical_entries = file_data.get("canonical_entries", ())
    file_path = file_data["file_path"]

    for entry_index, (key, source_text, line_num) in enumerate(file_data["parsed_entries"]):
        summary["total"] += 1
        file_summary["total"] += 1
        status, history_entry = diff_service.classify_entry(
            file_path, key, source_text, history_index, target_lang_code=target_lang_code
        )
        entry_info = {
            "key": key,
            "source": source_text,
            "line_num": line_num - 1,
            "translation": None,
            "is_dirty": False,
            "entry": canonical_entries[entry_index] if entry_index < len(canonical_entries) else None,
        }
        if status == "unchanged":
            summary["unchanged"] += 1
            file_summary["unchanged"] += 1
            entry_info["translation"] = history_entry["translation"] if history_entry else None
        else:
            summary[status] += 1
            file_summary[status] += 1
            reference_match = (
                reference_resolver.lookup(key, source_text, file_path)
                if reference_resolver is not None
                else None
            )
            if reference_match is not None and reference_match.hit:
                entry_info["translation"] = reference_match.translation
                entry_info["resolution"] = "reference"
                reference_protected_entries.append({"source_file": file_path, "key": key})
            else:
                entry_info["is_dirty"] = True
                entry_info["resolution"] = "model"
                texts_to_translate.append(source_text)
                key_delta_indices.append(len(full_file_entries))
            file_summary["dirty_entries"].append({
                "key": key,
                "status": status,
                "line_num": line_num,
                "source_text": source_text,
                "resolution": entry_info.get("resolution"),
            })
        full_file_entries.append(entry_info)

    return texts_to_translate, key_delta_indices, full_file_entries


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
        reference_resolver: Optional[Any] = None,
    ) -> Dict[str, Any]:
        summary = {"total": 0, "new": 0, "changed": 0, "unchanged": 0}
        file_tasks_for_ai: List[FileTask] = []
        processing_records: List[Dict[str, Any]] = []
        file_summaries: List[Dict[str, Any]] = []
        reference_protected_entries: List[Dict[str, str]] = []

        target_lang_code = target_lang_info["code"]
        lang_dest_dir = base_output_dir if total_targets == 1 else base_output_dir / target_lang_code
        num_files = len(current_files_data)

        for index, file_data in enumerate(current_files_data):
            filename = file_data["filename"]
            file_path = file_data["file_path"]
            file_summary = {
                "filename": filename,
                "file_path": file_path,
                "total": 0,
                "new": 0,
                "changed": 0,
                "unchanged": 0,
                "dirty_entries": [],
            }

            if progress_callback:
                pct = 20 + int((index / num_files) * 30)
                progress_callback({
                    "stage": "Comparing",
                    "stage_code": "comparing_entries",
                    "percent": pct,
                    "message": f"Comparing {filename} ({index + 1}/{num_files})",
                    "current_file": filename,
                    "current_file_index": index + 1,
                    "total_files": num_files,
                    "target_lang": target_lang_code,
                })

            texts_to_translate, key_delta_indices, full_file_entries = _prepare_file_entries(
                file_data,
                history_index,
                diff_service,
                target_lang_code,
                summary,
                file_summary,
                reference_resolver,
                reference_protected_entries,
            )

            processing_records.append({
                "fd": file_data,
                "full_file_entries": full_file_entries,
                "key_delta_indices": key_delta_indices,
            })
            file_summaries.append(file_summary)

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
            "file_summaries": file_summaries,
            "reference_protected_entries": reference_protected_entries,
            "reference_metrics": (
                reference_resolver.metrics()
                if reference_resolver is not None
                else {
                    "reference_enabled": False,
                    "reference_matched": 0,
                    "api_skipped": 0,
                }
            ),
        }
