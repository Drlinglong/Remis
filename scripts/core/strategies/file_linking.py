import os
import re
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class FileLinkingStrategy(ABC):
    """
    Abstract strategy for linking translation files to their source files.
    Decouples the logic of "which translation belongs to which source" from the service layer.
    """
    
    @abstractmethod
    def process_files(self, source_path: str, files: List[Dict[str, Any]], existing_tasks: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes a list of files and updates/creates tasks in the Kanban board.
        
        Args:
            source_path: The root path of the project source.
            files: List of file dictionaries (flat list from scanner).
            existing_tasks: The current tasks dictionary from the Kanban board (for preserving comments/status).
            
        Returns:
            A dictionary of tasks (mapped by file_id) ready to be saved to the board.
        """
        pass

class ParadoxFileLinkingStrategy(FileLinkingStrategy):
    """
    Implementation for Paradox Interactive games.
    Handles standard .yml -> _l_english.yml naming conventions.
    """

    def process_files(self, source_path: str, files: List[Dict[str, Any]], existing_tasks: Dict[str, Any]) -> Dict[str, Any]:
        new_tasks = {}
        
        # 1. Deduplicate input files by file_id
        seen_ids = set()
        unique_files = []
        for f in files:
            fid = f.get('file_id')
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                unique_files.append(f)

        # 2. Build Helper Maps
        # ID map for existing tasks to handle key migration
        id_to_key = {}
        for k, v in existing_tasks.items():
            internal_id = v.get('id')
            if internal_id:
                id_to_key[internal_id] = k

        # Map relative paths to Source Task IDs (for linking)
        rel_path_to_task_id = {} 

        # 3. First Pass: Source Files (The Parents)
        source_files = [f for f in unique_files if f['file_type'] == 'source']
        for f in source_files:
            file_id = f['file_id']
            file_path = f['file_path']
            
            # Calculate relative path for matching
            if file_path.startswith(source_path):
                rel_path = os.path.relpath(file_path, source_path)
            else:
                rel_path = os.path.basename(file_path)
                
            rel_path_to_task_id[rel_path.lower()] = file_id
            
            # Create or Update Task
            task = self._create_or_update_task(
                file_id, 
                f, 
                existing_tasks, 
                id_to_key, 
                file_type='source', 
                rel_path=rel_path
            )
            new_tasks[file_id] = task

        # 4. Second Pass: Translation Files (The Children)
        translation_files = [f for f in unique_files if f['file_type'] == 'translation']
        for tf in translation_files:
            file_id = tf['file_id']
            t_path = tf['file_path']
            t_name = os.path.basename(t_path)
            
            # Link Logic
            lang, parent_task_id = self._find_link(t_name, t_path, source_path, rel_path_to_task_id)
            
            task = self._create_or_update_task(
                file_id, 
                tf, 
                existing_tasks, 
                id_to_key, 
                file_type='translation',
                meta_extras={
                    "lang": lang,
                    "parent_task_id": parent_task_id,
                    "rel_path": os.path.relpath(t_path, source_path) if t_path.startswith(source_path) else t_name
                }
            )
            new_tasks[file_id] = task

        # 5. Third Pass: Metadata/Config Files
        meta_files = [f for f in unique_files if f.get('file_type') in ['metadata', 'config']]
        for mf in meta_files:
            file_id = mf['file_id']
            task = self._create_or_update_task(
                file_id, 
                mf, 
                existing_tasks, 
                id_to_key, 
                file_type=mf.get('file_type')
            )
            new_tasks[file_id] = task

        return new_tasks

    def _create_or_update_task(self, file_id, file_data, existing_tasks, id_to_key, file_type, rel_path=None, meta_extras=None):
        # Handle Key Migration
        old_task = None
        if file_id in existing_tasks:
            old_task = existing_tasks[file_id]
        elif file_id in id_to_key:
            # Task exists under a different key but same ID
            old_task = existing_tasks[id_to_key[file_id]]
        
        file_path = file_data['file_path']
        title = os.path.basename(file_path)
        
        if old_task:
            # Update existing
            task = old_task.copy() # Shallow copy
            task['id'] = file_id # Ensure ID is current
            task['title'] = title
            task['filePath'] = file_path
            
            # Update status only if provided in file_data (which comes from DB/Scan)
            # CAUTION: We usually want to keep the board's status unless the file scan indicates a change?
            # In current logic, we respect the incoming status (e.g. from DB)
            if 'status' in file_data:
                task['status'] = file_data['status']
                
            if 'meta' not in task: task['meta'] = {}
        else:
            # Create new
            task = {
                "id": file_id,
                "type": "file",
                "title": title,
                "filePath": file_path,
                "status": file_data.get('status', 'todo'),
                "comments": "",
                "priority": "medium",
                "meta": {}
            }
            
        # Update Meta
        task['meta']['file_type'] = file_type
        if 'line_count' in file_data:
            key = 'source_lines' if file_type == 'source' else 'lines'
            task['meta'][key] = file_data['line_count']
            
        if rel_path:
            task['meta']['rel_path'] = rel_path
            
        if meta_extras:
            task['meta'].update(meta_extras)
            
        return task

    def _find_link(self, t_name, t_path, source_path, rel_path_to_task_id):
        # Extract Language - Allow space or underscore separator
        lang_match = re.search(r"[\s_]l_(\w+)\.yml$", t_name, re.IGNORECASE)
        lang = lang_match.group(1).lower() if lang_match else "unknown"
        
        # Extract Stem - remove the separator + l_lang + .yml
        t_stem = re.sub(r"[\s_]l_(\w+)\.yml$", "", t_name, flags=re.IGNORECASE)
        
        # Find Parent
        parent_task_id = None
        for s_rel, tid in rel_path_to_task_id.items():
            s_name = os.path.basename(s_rel)
            # Apply same relaxed stem extraction to source files
            s_base = re.sub(r"[\s_]l_(\w+)\.yml$", "", s_name, flags=re.IGNORECASE)
            if s_base.lower() == t_stem.lower():
                parent_task_id = tid
                break
                
        return lang, parent_task_id
