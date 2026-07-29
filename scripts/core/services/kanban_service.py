import os
import json
import logging
from typing import List, Dict, Any, Optional
from scripts.core.project_json_manager import ProjectJsonManager
from scripts.core.strategies.file_linking import FileLinkingStrategy, ParadoxFileLinkingStrategy

logger = logging.getLogger(__name__)

class KanbanService:
    """
    Service to manage Kanban board state and logic.
    Strictly handles data manipulation (JSON Sidecar) and does NOT perform disk scanning.
    """

    def __init__(self, repository=None, linking_strategy: Optional[FileLinkingStrategy] = None):
        # Default to Paradox strategy if none provided
        self.linking_strategy = linking_strategy or ParadoxFileLinkingStrategy()
        self.repository = repository

    @staticmethod
    def get_board_read_only(source_path: str) -> Dict[str, Any]:
        """Read the board without creating or repairing the project sidecar."""
        sidecar_path = os.path.join(source_path, ".remis_project.json")
        try:
            with open(sidecar_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            board = payload.get("kanban", {}) if isinstance(payload, dict) else {}
            if not isinstance(board, dict):
                board = {}
        except (OSError, json.JSONDecodeError):
            board = {}

        default_columns = ["todo", "in_progress", "proofreading", "paused", "done"]
        columns = board.get("columns")
        return {
            **board,
            "columns": columns if isinstance(columns, list) and len(columns) >= 3 else default_columns,
            "tasks": board.get("tasks", {}) if isinstance(board.get("tasks"), dict) else {},
            "column_order": (
                board.get("column_order")
                if isinstance(board.get("column_order"), list)
                else default_columns
            ),
        }

    def preview_board_for_files(self, source_path: str, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Project current disk files onto the board without persisting reconciliation."""
        board = self.get_board_read_only(source_path)
        return {
            **board,
            "tasks": self.linking_strategy.process_files(
                source_path,
                files,
                board.get("tasks", {}),
            ),
        }

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

    async def update_file_status_sync(
        self,
        project_id: str,
        source_path: str,
        file_id: str,
        status: str,
        files: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Updates file status in the JSON sidecar only.
        """
        try:
            board = self.preview_board_for_files(source_path, files or [])
            tasks = board.get("tasks", {})
            
            target_key = None
            if file_id in tasks:
                target_key = file_id
            else:
                for tid, t_obj in tasks.items():
                    if t_obj.get('id') == file_id:
                        target_key = tid
                        break
            
            if target_key:
                # Synchronize ID if changed (e.g. migration)
                if target_key != file_id:
                    tasks[file_id] = tasks.pop(target_key)
                    target_key = file_id
                    logger.info(f"KanbanService: Aligned task key during status update: {file_id}")

                old_status = tasks[target_key].get('status')
                if old_status != status:
                    tasks[target_key]['status'] = status
                    self.save_board(source_path, board)
                    
            else:
                logger.warning(f"Task for file {file_id} not found in Kanban. Skipping JSON update.")

        except Exception as e:
            logger.error(f"Failed to sync kanban after individual file update: {e}")

    async def save_board_and_sync(self, project_id: str, source_path: str, kanban_data: Dict[str, Any]) -> None:
        """
        Saves kanban board state to the project sidecar only.
        """
        self.save_board(source_path, kanban_data)
        logger.info("Saved project-local kanban state for %s", project_id)
