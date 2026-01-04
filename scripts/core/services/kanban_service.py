import os
import logging
from typing import List, Dict, Any, Optional
from scripts.core.project_json_manager import ProjectJsonManager

logger = logging.getLogger(__name__)

class KanbanService:
    """
    Service to manage Kanban board state and logic.
    Strictly handles data manipulation (JSON Sidecar) and does NOT perform disk scanning.
    """

    def __init__(self):
        pass

    def get_board(self, source_path: str) -> Dict[str, Any]:
        """
        Retrieves the Kanban board data from the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            return json_manager.get_kanban_data()
        except Exception as e:
            logger.error(f"Failed to get kanban board for {source_path}: {e}")
            raise

    def save_board(self, source_path: str, kanban_data: Dict[str, Any]) -> None:
        """
        Saves the Kanban board data to the project's JSON sidecar.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            json_manager.save_kanban_data(kanban_data)
        except Exception as e:
            logger.error(f"Failed to save kanban board for {source_path}: {e}")
            raise

    def sync_files_to_board(self, source_path: str, files: List[Dict[str, Any]]) -> None:
        """
        Syncs a list of files (provided by an external scanner) to the Kanban board.
        Handles ID alignment and cleanup of obsolete file tasks.
        """
        try:
            json_manager = ProjectJsonManager(source_path)
            kanban_data = json_manager.get_kanban_data()
            tasks = kanban_data.get("tasks", {})
            columns = kanban_data.get("columns", [])
            
            # Robustness: Ensure default columns exist
            default_columns = ["todo", "in_progress", "proofreading", "paused", "done"]
            if len(columns) < 3:
                columns = default_columns
            
            # 1. Deduplicate input files by file_id to avoid accidental double processing
            seen_ids = set()
            unique_files = []
            for f in files:
                fid = f.get('file_id')
                if fid and fid not in seen_ids:
                    seen_ids.add(fid)
                    unique_files.append(f)
            
            # 2. ID Alignment Check (Fix "Ghost" duplication)
            # Ensure every task whose internal 'id' is in current scanner is keyed by that id
            # Also find tasks that use one of our current file_ids as internal ID but have a different dict Key
            id_to_key = {}
            for k, v in tasks.items():
                internal_id = v.get('id')
                if internal_id:
                    id_to_key[internal_id] = k

            # Map for current files for quick lookup
            scanned_ids = set(f['file_id'] for f in unique_files)

            # 3. Process Scanned Files
            import re
            rel_path_to_task_id = {} # For linking translations to sources
            
            # First pass: Source files (Main Tasks)
            for f in [f for f in unique_files if f['file_type'] == 'source']:
                file_id = f['file_id']
                file_path = f['file_path']
                rel_path = os.path.relpath(file_path, source_path) if file_path.startswith(source_path) else os.path.basename(file_path)
                rel_path_to_task_id[rel_path.lower()] = file_id

                # If task exists under a DIFFERENT key, migrate it
                if file_id in id_to_key and id_to_key[file_id] != file_id:
                    old_key = id_to_key[file_id]
                    tasks[file_id] = tasks.pop(old_key)
                    logger.info(f"KanbanService: Aligned task key {old_key} -> {file_id}")

                if file_id not in tasks:
                    tasks[file_id] = {
                        "id": file_id,
                        "type": "file",
                        "title": os.path.basename(file_path),
                        "filePath": file_path,
                        "status": f.get('status', 'todo'),
                        "comments": "",
                        "priority": "medium",
                        "meta": {
                            "source_lines": f.get('line_count', 0),
                            "file_type": "source",
                            "rel_path": rel_path
                        }
                    }
                else:
                    # Sync DB status if missing/outdated from scanner hydration? 
                    # Usually f['status'] is already hydrated from JSON in FileService. 
                    # But if DB was updated externally, we trust the DB record passed in 'files'.
                    tasks[file_id]["status"] = f.get('status', tasks[file_id].get('status', 'todo'))
                    tasks[file_id]["title"] = os.path.basename(file_path)
                    tasks[file_id]["filePath"] = file_path
                    if "meta" not in tasks[file_id]: tasks[file_id]["meta"] = {}
                    tasks[file_id]["meta"].update({
                        "source_lines": f.get('line_count', 0),
                        "file_type": "source",
                        "rel_path": rel_path
                    })

            # Second pass: Translation files (Linked Tasks)
            for tf in [f for f in unique_files if f['file_type'] == 'translation']:
                file_id = tf['file_id']
                t_path = tf['file_path']
                t_name = os.path.basename(t_path)
                
                # Link logic
                lang_match = re.search(r"_l_(\w+)\.yml$", t_name, re.IGNORECASE)
                lang = lang_match.group(1).lower() if lang_match else "unknown"
                t_stem = re.sub(r"_l_(\w+)\.yml$", "", t_name, flags=re.IGNORECASE)
                
                parent_task_id = None
                for s_rel, tid in rel_path_to_task_id.items():
                    s_name = os.path.basename(s_rel)
                    s_base = re.sub(r"_l_(\w+)\.yml$", "", s_name, flags=re.IGNORECASE)
                    if s_base.lower() == t_stem.lower():
                        parent_task_id = tid
                        break

                # Migrate if key mismatch
                if file_id in id_to_key and id_to_key[file_id] != file_id:
                    old_key = id_to_key[file_id]
                    tasks[file_id] = tasks.pop(old_key)

                if file_id not in tasks:
                    tasks[file_id] = {
                        "id": file_id,
                        "type": "file",
                        "title": t_name,
                        "filePath": t_path,
                        "status": tf.get('status', 'todo'),
                        "meta": {
                            "lines": tf.get('line_count', 0),
                            "file_type": "translation",
                            "lang": lang,
                            "parent_task_id": parent_task_id,
                            "rel_path": os.path.relpath(t_path, source_path) if t_path.startswith(source_path) else t_name
                        }
                    }
                else:
                    tasks[file_id]["status"] = tf.get('status', tasks[file_id].get('status', 'todo'))
                    if "meta" not in tasks[file_id]: tasks[file_id]["meta"] = {}
                    tasks[file_id]["meta"].update({
                        "lines": tf.get('line_count', 0),
                        "file_type": "translation",
                        "lang": lang,
                        "parent_task_id": parent_task_id
                    })

            # Third pass: Config/Metadata
            for mf in [f for f in unique_files if f.get('file_type') in ['metadata', 'config']]:
                file_id = mf['file_id']
                if file_id in id_to_key and id_to_key[file_id] != file_id:
                    old_key = id_to_key[file_id]
                    tasks[file_id] = tasks.pop(old_key)
                
                if file_id not in tasks:
                    tasks[file_id] = {
                        "id": file_id,
                        "type": "file",
                        "title": os.path.basename(mf['file_path']),
                        "filePath": mf['file_path'],
                        "status": mf.get('status', 'todo'),
                        "meta": { "file_type": mf.get('file_type') }
                    }
                else:
                    tasks[file_id]["status"] = mf.get('status', tasks[file_id].get('status', 'todo'))

            # 4. Cleanup Obsolete "file" Tasks
            # Keys that are NOT in current scanned IDs AND are of type 'file' should be removed
            keys_to_remove = []
            for tid, task in tasks.items():
                if task.get('type') == 'file':
                    task_internal_id = task.get('id')
                    if task_internal_id not in scanned_ids:
                        keys_to_remove.append(tid)
            
            for k in keys_to_remove:
                logger.info(f"KanbanService: Cleaning up obsolete file task {k} ({tasks[k].get('title')})")
                tasks.pop(k)

            # 5. Save Board
            json_manager.save_kanban_data({
                "columns": columns,
                "tasks": tasks,
                "column_order": kanban_data.get("column_order", columns)
            })
            logger.info(f"KanbanService: Synced board for {source_path}. Total tasks: {len(tasks)}")
            
        except Exception as e:
            logger.error(f"Failed to sync files to kanban: {e}")
            # Don't raise, just log error to avoid crashing the whole refresh process?
            # Or raise to let upper layer know? 
            # In PM code it was implicit. Let's log and re-raise.
            raise
